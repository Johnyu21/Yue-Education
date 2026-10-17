"""Compatibility entry. Both commands use the same application."""
from app.main import app

def create_app(config=None):
    if config is not None:
        raise ValueError("Configure M5 through environment before startup")
    return app
