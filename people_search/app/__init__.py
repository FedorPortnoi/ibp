import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-people-search')
    app.json.ensure_ascii = False

    csrf.init_app(app)

    from .routes.auth import auth_bp
    from .routes.search import search_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(search_bp)

    return app
