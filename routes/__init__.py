"""
Routes package initialization
"""

from routes.main import main
from routes.api import api

def register_blueprints(app):
    """Register all blueprints with the app"""
    app.register_blueprint(main)
    app.register_blueprint(api)