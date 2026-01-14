from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
from sqlalchemy.orm import Session
from sqlalchemy import event

db = SQLAlchemy()
INDEX = []
# Thread-safe lock for atomic index operations
INDEX_LOCK = threading.RLock()


def add_to_index(index_name, obj):
    """Atomic index update using lock to ensure thread safety."""
    with INDEX_LOCK:
        INDEX.append((index_name, obj.id, obj.body))


class SearchableMixin(object):
    """
    Fixed SearchableMixin that addresses all six defects:
    1. Defensive checks for _changes existence and type
    2. Proper cleanup and isolation of _changes per transaction
    3. Uses session.info (thread-safe) instead of shared db.session attributes
    4. Atomic index updates via lock mechanism
    5. Session-level event binding instead of db.session global binding
    6. Proper SQLAlchemy SessionEvents pattern
    """

    @classmethod
    def before_commit(cls, session):
        """
        Prepare transaction changes for indexing.
        Uses session.info to store changes in session-local storage (thread-safe).
        Clears any residual state at start of each transaction.
        """
        # Initialize/clear session-local storage at start of transaction
        if 'searchable_changes' not in session.info:
            session.info['searchable_changes'] = {}
        else:
            # Clear residual state from previous transaction
            session.info['searchable_changes'] = {}

        # Store current transaction changes in session.info (thread-safe, transaction-scoped)
        session.info['searchable_changes'] = {
            'add': [obj for obj in session.new if isinstance(obj, cls)],
            'update': [obj for obj in session.dirty if isinstance(obj, cls)],
            'delete': [obj for obj in session.deleted if isinstance(obj, cls)]
        }

    @classmethod
    def after_commit(cls, session):
        """
        Process index updates after successful commit.
        Defensively checks for _changes existence and type.
        Cleans up after processing to prevent stale data accumulation.
        """
        # Defensive check: ensure searchable_changes exists and is dict
        if 'searchable_changes' not in session.info:
            return
        
        changes = session.info.get('searchable_changes')
        if not isinstance(changes, dict):
            return

        # Defensively check each key exists before iteration
        if 'add' in changes:
            for obj in changes['add']:
                add_to_index(cls.__tablename__, obj)
        
        if 'update' in changes:
            for obj in changes['update']:
                add_to_index(cls.__tablename__, obj)
        
        if 'delete' in changes:
            for obj in changes['delete']:
                add_to_index(cls.__tablename__, obj)

        # Clean up after commit to prevent stale data
        session.info['searchable_changes'] = {}

    @classmethod
    def after_rollback(cls, session):
        """
        Clean up after rollback to ensure state isolation.
        Prevents rollback changes from affecting next transaction.
        """
        if 'searchable_changes' in session.info:
            session.info['searchable_changes'] = {}


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Session-level event binding (fixed Problem 6)
# This uses SQLAlchemy's recommended event binding pattern for Session class
# instead of binding to global db.session instance
event.listens_for(Session, 'before_commit')(Post.before_commit)
event.listens_for(Session, 'after_commit')(Post.after_commit)
event.listens_for(Session, 'after_rollback')(Post.after_rollback)
