from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import Session
import threading

# Application-wide DB instance
db = SQLAlchemy()

# Mock index storage (thread-safe via LOCK)
INDEX = []
_INDEX_LOCK = threading.Lock()


def atomic_add_to_index(index_name, obj):
    """Atomically add an index entry to the mock INDEX list."""
    with _INDEX_LOCK:
        # Simulate an index write that shouldn't interleave with other commits
        INDEX.append((index_name, obj.id, obj.body))


class SearchableMixin(object):
    """Mixin which keeps a session-scoped record of objects to index.

    - Uses session.info (dict) for session-scoped storage.
    - Guards type checks to avoid AttributeError/TypeError.
    """

    @staticmethod
    def _init_changes(session):
        # Ensure we have a session-local, well-typed place to store changes.
        if 'search_changes' not in session.info or not isinstance(session.info['search_changes'], dict):
            session.info['search_changes'] = {'add': [], 'update': [], 'delete': []}
        else:
            # Reinitialize per-transaction to avoid residual/stale data.
            session.info['search_changes'].clear()
            session.info['search_changes'].update({'add': [], 'update': [], 'delete': []})

    @classmethod
    def before_commit(cls, session):
        """Collect Searchable objects in the current transaction into session.info.

        This is called by a Session-level event; the method is tolerant to missing
        attributes and reinitializes storage for each transaction.
        """
        # Reset or create a new changes structure for every transaction (isolated)
        SearchableMixin._init_changes(session)

        def add_if_searchable(obj, kind):
            # A defensive check - some objects may not be SQLAlchemy models
            if hasattr(obj, '__tablename__'):
                session.info['search_changes'][kind].append(obj)

        # Collect per-transaction changes at a session level (safe)
        for obj in session.new:
            add_if_searchable(obj, 'add')
        for obj in session.dirty:
            add_if_searchable(obj, 'update')
        for obj in session.deleted:
            add_if_searchable(obj, 'delete')

    @classmethod
    def after_commit(cls, session):
        """Apply index updates in a safe, atomic manner.

        The function defensively validates session.info['search_changes']. If present,
        it iterates and applies updates to the mock index in an atomic block.
        After processing the index, it clears the session storage to avoid leaks.
        """
        changes = session.info.get('search_changes')

        # Defensive checks: ensure changes exist and have correct shape
        if not changes or not isinstance(changes, dict):
            return

        # Apply index additions atomically, preserving ordering within this
        # single transaction. We use a lock to avoid races with other threads.
        for obj in changes.get('add', []):
            atomic_add_to_index(getattr(obj, '__tablename__', 'unknown'), obj)
        for obj in changes.get('update', []):
            atomic_add_to_index(getattr(obj, '__tablename__', 'unknown'), obj)
        for obj in changes.get('delete', []):
            atomic_add_to_index(getattr(obj, '__tablename__', 'unknown'), obj)

        # cleanup to avoid stale data (defensive and session-safe)
        session.info.pop('search_changes', None)

    @classmethod
    def after_rollback(cls, session):
        # Ensure no stale state remains after a rollback
        if 'search_changes' in session.info:
            session.info.pop('search_changes', None)


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Register Session-level events using SQLAlchemy's event system.
# This ensures the events fire for every Session instance (recommended pattern).
@event.listens_for(Session, 'before_commit')
def _session_before_commit(session):
    # Call SearchableMixin.before_commit for all registered models.
    # We can call it generically because it uses defensive checks.
    SearchableMixin.before_commit(session)


@event.listens_for(Session, 'after_commit')
def _session_after_commit(session):
    SearchableMixin.after_commit(session)


@event.listens_for(Session, 'after_rollback')
def _session_after_rollback(session):
    SearchableMixin.after_rollback(session)
