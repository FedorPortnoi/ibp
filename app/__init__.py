"""
IBP - Identity-Based Profiler
=============================
Flask application factory with Buratino-style workflow.
"""

import os
import logging
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize extensions
db = SQLAlchemy()

logger = logging.getLogger('ibp')


def create_app(config_name='development'):
    """Application factory for IBP."""

    # Setup structured logging
    from app.utils.logger import setup_logging
    setup_logging(log_level='INFO')

    app = Flask(__name__)

    # Load configuration
    if config_name == 'development':
        app.config['DEBUG'] = True
        app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ibp.db')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')

        # VK API configuration
        app.config['VK_SERVICE_TOKEN'] = os.environ.get('VK_SERVICE_TOKEN')
        app.config['VK_API_VERSION'] = os.environ.get('VK_API_VERSION', '5.199')

        # Search4Faces API (optional)
        app.config['SEARCH4FACES_API_KEY'] = os.environ.get('SEARCH4FACES_API_KEY')

    # Initialize extensions with app
    db.init_app(app)

    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Import and register blueprints directly from each file
    from app.routes.main import main_bp
    from app.routes.phase1 import phase1_bp
    from app.routes.phase2 import phase2_bp
    from app.routes.phase3 import phase3_bp
    from app.routes.report import report_bp
    from app.routes.phase4 import phase4_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(phase1_bp)
    app.register_blueprint(phase2_bp)
    app.register_blueprint(phase3_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(phase4_bp)

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
