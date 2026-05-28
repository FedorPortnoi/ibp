"""
IBP - Identity-Based Profiler
=============================
Flask application factory with Buratino-style workflow.
"""

import os
import logging
from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
)

logger = logging.getLogger('ibp')


def create_app(config_name=None):
    """Application factory for IBP."""

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    # Setup structured logging
    from app.utils.logger import setup_logging
    setup_logging(log_level='INFO')

    app = Flask(__name__)

    # Trust X-Forwarded-For from nginx reverse proxy (1 proxy hop).
    # MUST be applied BEFORE limiter.init_app() so that get_remote_address()
    # returns the real client IP instead of 127.0.0.1 from nginx.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Ensure JSON responses contain proper UTF-8 Cyrillic (not Unicode escapes)
    app.json.ensure_ascii = False

    # 1) Load static config from Config classes (DEBUG, TESTING, paths, etc.)
    from config import config as config_map, load_env_config
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # 2) Load ALL API keys fresh from os.environ (not frozen class attributes).
    #    This is the fix for VK_SERVICE_TOKEN not loading in production:
    #    class attributes are evaluated once at import time and cached by Python,
    #    so they can miss env vars set later or differ between environments.
    load_env_config(app)

    # Validate SECRET_KEY is set
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Set it in your .env file or environment before running the app."
        )

    # Testing overrides
    if config_name == 'testing':
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['RATELIMIT_ENABLED'] = False

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    # DoS/DDoS protection middleware (Layer 3 — behavioral analysis)
    from app.middleware.dos_protection import init_dos_protection
    init_dos_protection(app)

    # Create required directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'reports'), exist_ok=True)

    # Import and register blueprints directly from each file
    from app.routes.auth import auth_bp
    from app.routes.admin_users import admin_users_bp
    from app.routes.main import main_bp
    from app.routes.candidate_check import candidate_bp
    from app.routes.subscribe import subscribe_bp
    from app.routes.chat import chat_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(subscribe_bp)
    app.register_blueprint(chat_bp)

    # Global auth check — protect ALL routes except login, register, and static files
    @app.before_request
    def check_auth():
        allowed_endpoints = {
            'auth.login', 'auth.logout', 'auth.register',
            'auth.set_lang', 'static', 'main.health_check',
            'main.readiness_check', 'main.privacy',
        }
        # Subscribe endpoints are public for logged-in users (no subscription needed)
        subscribe_endpoints = {
            'subscribe.subscribe_page', 'subscribe.pay',
            'subscribe.success', 'subscribe.status',
        }
        if request.endpoint and (
            request.endpoint in allowed_endpoints or
            request.endpoint.startswith('static')
        ):
            return

        if request.path.endswith('favicon.ico'):
            return

        if not session.get('user_id'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Требуется авторизация', 'redirect': '/login'}), 401
            if 'favicon' not in request.path and not request.path.startswith('/static'):
                session['next_url'] = request.path
            return redirect(url_for('auth.login'))

        # Activity-based session timeout (default 1h inactivity)
        import datetime as _dt
        last_active = session.get('last_active')
        if last_active:
            try:
                last_dt = _dt.datetime.fromisoformat(last_active)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=_dt.timezone.utc)
                idle_limit = int(os.environ.get('IBP_SESSION_TIMEOUT', 3600))
                if (_dt.datetime.now(_dt.timezone.utc) - last_dt).total_seconds() > idle_limit:
                    session.clear()
                    if request.is_json:
                        return jsonify({'error': 'Сессия истекла', 'redirect': '/login'}), 401
                    return redirect(url_for('auth.login'))
            except (ValueError, TypeError):
                pass
        session['last_active'] = _dt.datetime.now(_dt.timezone.utc).isoformat()

        # Subscription / free-tier check
        # Free tier: users get 2 checks per week without paying.
        # Paid subscription: unlimited. Admin: always unlimited.
        if request.endpoint and request.endpoint not in subscribe_endpoints:
            from app.models.user import User
            from app.models.subscription import Subscription
            user = User.query.get(session['user_id'])
            if user and not user.is_admin:
                sub = Subscription.query.filter_by(user_id=user.id).first()
                # Auto-create subscription row for new users (free tier)
                if not sub:
                    sub = Subscription(user_id=user.id, status='inactive')
                    db.session.add(sub)
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                # Free tier users can browse the app freely.
                # Limit is enforced at /candidate/start (see candidate_check.py).

    # Inject current_user + subscription into all templates
    @app.context_processor
    def inject_user():
        from app.routes.auth import get_current_user
        from app.models.subscription import Subscription
        user = get_current_user()
        sub = None
        if user:
            sub = Subscription.query.filter_by(user_id=user.id).first()
        return {'current_user': user, 'user_subscription': sub}

    # Security headers on all responses
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(), payment=(), usb=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://unpkg.com https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://unpkg.com https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' https://cdnjs.cloudflare.com; "
            "frame-ancestors 'none'"
        )
        # Remove server fingerprint headers
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)
        return response

    # Register error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"500 error: {e}", exc_info=True)
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        retry_after = int(getattr(e, 'retry_after', 60) or 60)
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': 'Слишком много запросов. Попробуйте позже.',
                'retry_after': retry_after,
            }), 429
        return render_template('errors/500.html'), 429

    # Create database tables (new columns added via: flask db upgrade)
    with app.app_context():
        db.create_all()
        logger.info("Database tables created successfully")

    return app
