"""
IBP - Identity-Based Profiler
=============================
Flask application factory with Buratino-style workflow.
"""

import os
import logging
from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize extensions
db = SQLAlchemy()

logger = logging.getLogger('ibp')


def create_app(config_name=None):
    """Application factory for IBP."""

    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    # Setup structured logging
    from app.utils.logger import setup_logging
    setup_logging(log_level='INFO')

    app = Flask(__name__)

    # Load configuration
    secret_key = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY environment variable is not set. "
            "Set it in your .env file or environment before running the app."
        )
    app.config['SECRET_KEY'] = secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ibp.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')

    # VK API configuration
    app.config['VK_SERVICE_TOKEN'] = os.environ.get('VK_SERVICE_TOKEN')
    app.config['VK_API_VERSION'] = os.environ.get('VK_API_VERSION', '5.199')

    # Search4Faces API (optional)
    app.config['SEARCH4FACES_API_KEY'] = os.environ.get('SEARCH4FACES_API_KEY')

    if config_name == 'production':
        app.config['DEBUG'] = False
        app.config['TESTING'] = False
        app.config['SESSION_COOKIE_SECURE'] = False  # Render handles HTTPS at edge
    else:
        app.config['DEBUG'] = True

    # Initialize extensions with app
    db.init_app(app)

    # Create required directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'reports'), exist_ok=True)

    # Import and register blueprints directly from each file
    from app.routes.auth import auth_bp, is_auth_enabled
    from app.routes.main import main_bp
    from app.routes.phase1 import phase1_bp
    from app.routes.phase2 import phase2_bp
    from app.routes.phase3 import phase3_bp
    from app.routes.report import report_bp
    from app.routes.phase4 import phase4_bp
    from app.routes.scoring import scoring_bp
    from app.routes.connections import connections_bp
    from app.routes.timeline import timeline_bp
    from app.routes.dossier import dossier_bp
    from app.routes.api_search import api_search_bp
    from app.routes.candidate_check import candidate_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(phase1_bp)
    app.register_blueprint(phase2_bp)
    app.register_blueprint(phase3_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(phase4_bp)
    app.register_blueprint(scoring_bp)
    app.register_blueprint(connections_bp)
    app.register_blueprint(timeline_bp)
    app.register_blueprint(dossier_bp)
    app.register_blueprint(api_search_bp)
    app.register_blueprint(candidate_bp)

    # Global auth check — protect ALL routes except login and static files
    @app.before_request
    def check_auth():
        if not is_auth_enabled():
            return

        allowed_endpoints = {'auth.login', 'auth.logout', 'static', 'main.health_check'}
        if request.endpoint and (
            request.endpoint in allowed_endpoints or
            request.endpoint.startswith('static')
        ):
            return

        if request.path.endswith('favicon.ico'):
            return

        if not session.get('authenticated'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Требуется авторизация', 'redirect': '/login'}), 401
            if 'favicon' not in request.path and not request.path.startswith('/static'):
                session['next_url'] = request.url
            return redirect(url_for('auth.login'))

    # Register error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"500 error: {e}", exc_info=True)
        return render_template('errors/500.html', error=str(e)), 500

    # Create database tables
    with app.app_context():
        db.create_all()
        logger.info("Database tables created successfully")

    return app
