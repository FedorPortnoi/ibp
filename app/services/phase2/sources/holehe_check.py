"""
Holehe Email Registration Check
================================
Checks which online services an email address is registered on.
Uses the holehe library (121 modules, async httpx + trio).

Tier: B (Verification) -- confirms email existence across services.

Holehe is SLOW (~30-60s per email) so we limit to top 5 candidates.
Each confirmed registration is evidence the email is real + active.

Requires: pip install holehe
"""

import logging
import threading
from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType

logger = logging.getLogger(__name__)


def _run_holehe_sync(email: str, timeout: float = 45.0) -> list:
    """
    Run holehe check synchronously by spawning trio in a new thread.

    Returns list of dicts: [{'name': 'spotify', 'exists': True, ...}, ...]
    """
    import trio
    import httpx

    results = []

    async def _check(email_addr):
        from holehe.core import get_functions, import_submodules
        import holehe.modules

        modules = import_submodules(holehe.modules)
        websites = get_functions(modules)

        out = []
        async with httpx.AsyncClient(timeout=timeout) as client:
            for website_func in websites:
                try:
                    await website_func(email_addr, client, out)
                except Exception:
                    pass  # Individual module failures are expected
        return out

    # trio.run() blocks the calling thread, which is fine in our ThreadPoolExecutor
    try:
        results = trio.run(_check, email)
    except Exception as e:
        logger.warning(f"Holehe trio.run error for {email}: {e}")

    return results


class HoleheCheckSource(BaseSource):
    """
    Check which online services an email is registered on using Holehe.

    This is a VERIFICATION source — it confirms that an email address
    is real and actively used by checking registration across 120+ services.

    Slow but valuable: if holehe finds registrations, the email is definitely real.
    """

    name = "Holehe Email Check"
    source_type = SourceType.VERIFICATION
    source_tier = SourceTier.B
    requires_api_key = False
    rate_limit_per_minute = 5  # Very slow, ~30-60s per email

    MAX_EMAILS = 5  # Limit due to slowness
    TIMEOUT_PER_EMAIL = 45.0

    def is_available(self) -> bool:
        """Check if holehe library is installed."""
        try:
            import holehe
            return True
        except ImportError:
            return False

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        results = []

        # Collect emails to check
        emails_to_check = []
        if email:
            if isinstance(email, list):
                emails_to_check.extend(email)
            else:
                emails_to_check.append(email)

        # Also accept email_candidates from pipeline
        email_candidates = kwargs.get('email_candidates', [])
        for candidate in email_candidates:
            if isinstance(candidate, dict):
                addr = candidate.get('email', '')
            else:
                addr = str(candidate)
            if addr and addr not in emails_to_check:
                emails_to_check.append(addr)

        # Limit to top N (holehe is very slow)
        emails_to_check = emails_to_check[:self.MAX_EMAILS]

        if not emails_to_check:
            return results

        self.logger.info(f"Holehe checking {len(emails_to_check)} emails: {emails_to_check}")

        for email_addr in emails_to_check:
            try:
                holehe_results = _run_holehe_sync(email_addr, self.TIMEOUT_PER_EMAIL)

                # Filter to services where the email IS registered
                registered = [
                    r for r in holehe_results
                    if isinstance(r, dict) and r.get('exists') is True
                ]

                if registered:
                    services = [r.get('name', 'unknown') for r in registered]

                    # More registrations = higher confidence the email is real
                    if len(services) >= 5:
                        confidence = 0.90
                    elif len(services) >= 3:
                        confidence = 0.85
                    elif len(services) >= 1:
                        confidence = 0.80
                    else:
                        confidence = 0.70

                    results.append(SourceResult(
                        data_type='email',
                        value=email_addr,
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=confidence,
                        verified=True,
                        metadata={
                            'registered_services': services[:20],
                            'total_registered': len(registered),
                            'total_checked': len(holehe_results),
                            'verification': 'holehe_confirmed',
                        },
                    ))

                    # Also emit individual service profiles as discoveries
                    for svc in registered[:10]:
                        svc_name = svc.get('name', '')
                        svc_domain = svc.get('domain', '')
                        if svc_domain:
                            results.append(SourceResult(
                                data_type='profile',
                                value=f"https://{svc_domain}",
                                source_name=self.name,
                                source_tier=self.source_tier,
                                confidence=0.80,
                                verified=True,
                                metadata={
                                    'platform': svc_name,
                                    'email_used': email_addr,
                                    'verification': 'holehe_registration',
                                },
                            ))

                    self.logger.info(
                        f"Holehe: {email_addr} registered on {len(registered)} services: "
                        f"{services[:5]}"
                    )
                else:
                    self.logger.debug(f"Holehe: {email_addr} not found on any service")

            except Exception as e:
                self.logger.warning(f"Holehe check error for {email_addr}: {e}")

        return results
