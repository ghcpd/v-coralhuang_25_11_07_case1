"""
Flask app configuration and initialization for testing.
"""
import pytest
from flask import Flask
from models import db


@pytest.fixture(scope='function')
def app():
    """Create fresh application for each test."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(autouse=True)
def app_context(app):
    """Provide application context for each test."""
    with app.app_context():
        yield
