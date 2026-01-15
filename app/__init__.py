"""
IBP - Identity-Based Profiler
=============================
Flask application factory.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Initialize extensions
db = SQLAlchemy()


def create_app(config_name='development'):
    """Application factory for IBP."""
    
    app = Flask(__name__)
    
    # Load configuration
    if config_name == 'development':
        app.config['DEBUG'] = True
        app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ibp.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    
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
    
    app.register_blueprint(main_bp)
    app.register_blueprint(phase1_bp)
    app.register_blueprint(phase2_bp)
    app.register_blueprint(phase3_bp)
    app.register_blueprint(report_bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully!")
    
    return app
