"""
DoS/DDoS protection middleware.
Tracks suspicious patterns and auto-bans repeat offenders.
"""
import os
import time
import threading
from collections import defaultdict, deque
from flask import request, jsonify
import logging

logger = logging.getLogger('ibp.dos')


def _get_client_ip() -> str:
    """Get the real client IP, accounting for nginx reverse proxy.

    Priority:
      1. request.remote_addr (correct when ProxyFix is applied)
      2. X-Forwarded-For header first entry (fallback)
      3. X-Real-IP header (nginx-specific fallback)
      4. "unknown"
    """
    # ProxyFix rewrites remote_addr from X-Forwarded-For, so this should
    # already be the real client IP.  Guard against it being the loopback
    # (means ProxyFix isn't active or nginx didn't send the header).
    ip = request.remote_addr
    if ip and ip not in ("127.0.0.1", "::1"):
        return ip

    # Fallback: parse X-Forwarded-For ourselves
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # First entry is the original client
        return xff.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()

    return ip or "unknown"


class DosProtection:
    def __init__(self):
        self._lock = threading.Lock()
        # IP -> list of request timestamps
        self._requests = defaultdict(lambda: deque(maxlen=1000))
        # IP -> ban expiry timestamp
        self._banned = {}
        # IP -> 404 count (rolling window)
        self._404s = defaultdict(lambda: deque(maxlen=100))
        # IP -> suspicious score
        self._scores = defaultdict(int)
        self._redis = None

    def _cleanup(self):
        """Remove expired bans and old request data."""
        now = time.time()
        with self._lock:
            # Clear expired bans
            expired = [ip for ip, exp in self._banned.items() if exp < now]
            for ip in expired:
                del self._banned[ip]
                self._scores.pop(ip, None)

            # Clear stale request data (no activity in 5 min)
            stale = []
            for ip, reqs in self._requests.items():
                if reqs and (now - reqs[-1]) > 300:
                    stale.append(ip)
            for ip in stale:
                del self._requests[ip]
                self._404s.pop(ip, None)

    def is_banned(self, ip: str) -> bool:
        if self._redis:
            try:
                return bool(self._redis.exists(f'ibp:ban:{ip}'))
            except Exception:
                pass
        now = time.time()
        with self._lock:
            return ip in self._banned and self._banned[ip] > now

    def ban(self, ip: str, duration: int = 3600):
        """Ban IP for duration seconds."""
        if self._redis:
            try:
                self._redis.setex(f'ibp:ban:{ip}', duration, '1')
                logger.warning(f"Banned {ip} for {duration}s (Redis shared)")
                return
            except Exception:
                pass
        with self._lock:
            self._banned[ip] = time.time() + duration
        logger.warning(f"Banned {ip} for {duration}s (in-memory, not shared across workers)")

    def record_request(self, ip: str) -> bool:
        """Record request from IP. Returns True if should be blocked."""
        now = time.time()

        with self._lock:
            # Check ban
            if ip in self._banned and self._banned[ip] > now:
                return True

            # Record timestamp
            reqs = self._requests[ip]
            reqs.append(now)

            # Check rates at different windows
            window_1s = sum(1 for t in reqs if now - t < 1)
            window_10s = sum(1 for t in reqs if now - t < 10)
            window_60s = sum(1 for t in reqs if now - t < 60)

            # Score suspicious behavior
            if window_1s > 20:       # >20 req/sec = bot
                self._scores[ip] += 10
            elif window_1s > 10:     # >10 req/sec = suspicious
                self._scores[ip] += 3
            elif window_10s > 50:    # >50 req/10sec
                self._scores[ip] += 2
            elif window_60s > 200:   # >200 req/min
                self._scores[ip] += 1

            # Auto-ban thresholds
            score = self._scores[ip]
            if score >= 20:
                self._banned[ip] = now + 86400   # 24h ban
                logger.warning(f"Auto-banned {ip} for 24h (score={score})")
                return True
            elif score >= 10:
                self._banned[ip] = now + 3600    # 1h ban
                logger.warning(f"Auto-banned {ip} for 1h (score={score})")
                return True
            elif score >= 5:
                self._banned[ip] = now + 300     # 5min ban
                logger.warning(f"Auto-banned {ip} for 5min (score={score})")
                return True

        return False

    def record_404(self, ip: str):
        """Scanner/fuzzer detection via 404 frequency."""
        now = time.time()
        with self._lock:
            q = self._404s[ip]
            q.append(now)
            # Count 404s in last 60 seconds
            recent = sum(1 for t in q if now - t < 60)
            if recent > 30:
                self._banned[ip] = now + 3600
                logger.warning(f"Scanner detected {ip} ({recent} 404s/min), banned 1h")

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "banned_ips": len([ip for ip, exp in self._banned.items() if exp > time.time()]),
                "tracked_ips": len(self._requests),
            }


# Global instance
_dos = DosProtection()


def get_dos_protection() -> DosProtection:
    """Get the global DosProtection instance."""
    return _dos


def init_dos_protection(app):
    """Register DoS protection middleware with Flask app."""

    # Disable in testing mode (same as Flask-Limiter RATELIMIT_ENABLED=False)
    if app.config.get('TESTING'):
        logger.info("DoS protection skipped (testing mode)")
        return

    import os as _os
    redis_url = app.config.get('REDIS_URL') or _os.environ.get('REDIS_URL')
    if redis_url:
        try:
            import redis as _redis_lib
            _rc = _redis_lib.from_url(redis_url, socket_connect_timeout=2)
            _rc.ping()
            _dos._redis = _rc
            logger.info("DoS protection: using Redis for shared ban state across workers")
        except Exception as _e:
            logger.warning(f"DoS protection: Redis unavailable ({_e}), using per-worker in-memory state")
    else:
        logger.warning(
            "DoS protection: REDIS_URL not set — ban state is NOT shared across Gunicorn workers. "
            "Set REDIS_URL=redis://localhost:6379/0 in production for proper multi-worker protection."
        )

    @app.before_request
    def check_dos():
        # Skip static files
        if request.path.startswith('/static'):
            return

        ip = _get_client_ip()

        if _dos.is_banned(ip):
            return jsonify({
                "error": "Доступ временно ограничен. Попробуйте позже."
            }), 429

        if _dos.record_request(ip):
            return jsonify({
                "error": "Слишком много запросов. Доступ временно ограничен."
            }), 429

    @app.after_request
    def track_404s(response):
        if response.status_code == 404:
            ip = _get_client_ip()
            _dos.record_404(ip)
        return response

    # Cleanup daemon thread
    def cleanup_loop():
        while True:
            time.sleep(300)
            _dos._cleanup()

    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()

    logger.info("DoS protection middleware initialized")
