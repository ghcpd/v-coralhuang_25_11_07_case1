from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.orm import Session as SessionClass
from datetime import datetime
import threading
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app and SQLAlchemy db instance
app = Flask(__name__)
# Use a file-backed SQLite DB shared across threads for tests
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Allow SQLite connections from multiple threads in tests
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'check_same_thread': False}}

db = SQLAlchemy(app)

# A simple in-memory mock index and a lock to provide atomic updates
INDEX = []
_INDEX_LOCK = threading.Lock()

def add_to_index(index_name, obj):
    # Atomic index update via a lock
    with _INDEX_LOCK:
        INDEX.append((index_name, obj.id, obj.body))

class SearchableMixin(object):
    @classmethod
    def _gather_changes(cls, session):
        # Only gather objects belonging to this class
        add = [obj for obj in session.new if isinstance(obj, cls)]
        update = [obj for obj in session.dirty if isinstance(obj, cls)]
        delete = [obj for obj in session.deleted if isinstance(obj, cls)]
        return {'add': add, 'update': update, 'delete': delete}

    @classmethod
    def before_commit(cls, session):
        # Defensive: always initialize storage in session.info (per-session state)
        try:
            session_info = session.info
        except Exception:
            # If the session has no info attribute, skip
            return

        # Initialize/clear the per-session searchable changes
        session_info['searchable_changes'] = cls._gather_changes(session)

    @classmethod
    def after_commit(cls, session):
        try:
            changes = session.info.get('searchable_changes')
        except Exception:
            # If no per-session info is available, nothing to do
            changes = None

        # Defensive checks: ensure it's a dict-like structure
        if not isinstance(changes, dict):
            # Nothing to index
            return

        # Apply indexing atomically using the lock inside add_to_index
        try:
            for obj in changes.get('add', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('update', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('delete', []):
                add_to_index(cls.__tablename__, obj)
        finally:
            # Always cleanup residual state whether successful or not
            session.info.pop('searchable_changes', None)

    @classmethod
    def after_rollback(cls, session):
        # Ensure we clean up on rollbacks too
        try:
            session.info.pop('searchable_changes', None)
        except Exception:
            pass


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Use SQLAlchemy's session-level event bindings instead of binding to a global session
# This ensures the handlers apply to any created Session and do not attach state to a shared 'db.session' object.

@event.listens_for(SessionClass, 'before_commit')
def session_before_commit(session):
    # For each mapped class that uses SearchableMixin, gather changes.
    # For simplicity we assume Post is the only searchable class in this test.
    Post.before_commit(session)

@event.listens_for(SessionClass, 'after_commit')
def session_after_commit(session):
    Post.after_commit(session)

@event.listens_for(SessionClass, 'after_rollback')
def session_after_rollback(session):
    Post.after_rollback(session)
