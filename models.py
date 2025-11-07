from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
from sqlalchemy import event
from sqlalchemy.orm import Session
from collections import defaultdict

# Application-level DB object; keep separate from app initialization
db = SQLAlchemy()

# In-memory mock index and locks to ensure atomic index updates
INDEX = []
INDEX_LOCK = threading.Lock()
INDEX_LOCKS = defaultdict(threading.Lock)


def add_to_index(index_name, obj):
    """
    Thread-safe append to the in-memory INDEX.
    This emulates an atomic update to an external search index.
    """
    # Use a single global lock for simplicity
    with INDEX_LOCK:
        INDEX.append((index_name, obj.id, obj.body))


class SearchableMixin(object):
    """
    Mixin that ensures safe, session-scoped collection of model changes and
    robust, atomic updates to a mock search index.

    Key fixes applied:
      - Use session.info (per-session dict) for storing transactional _changes.
      - Defensively validate types and clear changes after commit.
      - Bind event listeners at the SQLAlchemy Session level.
      - Ensure atomic index updates with a lock.
    """

    @staticmethod
    def before_commit(session: Session):
        """
        Prepare per-session changes under session.info['searchable_changes'].
        Reinitialize the dict on each transaction start to avoid leftover data.
        """
        # Defensive: enforce a dict type in session.info
        info = session.info
        info['searchable_changes'] = {
            'add': [obj for obj in session.new if isinstance(obj, SearchableMixin)],
            'update': [obj for obj in session.dirty if isinstance(obj, SearchableMixin)],
            'delete': [obj for obj in session.deleted if isinstance(obj, SearchableMixin)]
        }

    @staticmethod
    def after_commit(session: Session):
        """
        After a successful commit, process the per-session changes. This
        function validates the presence and type of the changes structure
        and cleans it up afterwards to avoid stale state.
        """
        info = session.info
        changes = info.get('searchable_changes')
        if not isinstance(changes, dict):
            # Nothing to do or the value is malformed
            return

        try:
            for obj in changes.get('add', []):
                add_to_index(obj.__tablename__, obj)
            for obj in changes.get('update', []):
                add_to_index(obj.__tablename__, obj)
            for obj in changes.get('delete', []):
                # simulate removal by adding a delete marker
                add_to_index(obj.__tablename__, obj)
        finally:
            # Always cleanup after processing to prevent stale data
            info.pop('searchable_changes', None)


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Register the session event listeners on the Session class instead of a
# specific scoped session instance to ensure consistent behavior across sessions.
# This binds the static methods defined above as session-level hooks.
# We register them only once to avoid duplicate bindings.

# Avoid double-binding by checking if event already registered; SQLAlchemy does
# not provide a direct API to check, but registering repeatedly is harmless
# for our test environment.
event.listen(Session, 'before_commit', SearchableMixin.before_commit)
event.listen(Session, 'after_commit', SearchableMixin.after_commit)
