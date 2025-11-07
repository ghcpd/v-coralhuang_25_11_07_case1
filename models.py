from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
from sqlalchemy import event
from sqlalchemy.orm import Session

# Initialize SQLAlchemy extension (app will call init_app)
db = SQLAlchemy()

# Thread-safe mock index using a lock to ensure atomic updates and preserve ordering
class MockIndex:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries = []

    def add(self, index_name, obj):
        with self._lock:
            # Simulate atomic index write
            self._entries.append((index_name, obj.id, obj.body))

    def clear(self):
        with self._lock:
            self._entries.clear()

    def all(self):
        with self._lock:
            return list(self._entries)


INDEX = MockIndex()


def add_to_index(index_name, obj):
    INDEX.add(index_name, obj)


class SearchableMixin(object):
    @classmethod
    def _collect_changes(cls, session):
        # Collect only instances of this class from the session's transactional state
        adds = [obj for obj in session.new if isinstance(obj, cls)]
        updates = [obj for obj in session.dirty if isinstance(obj, cls)]
        deletes = [obj for obj in session.deleted if isinstance(obj, cls)]
        return {'add': adds, 'update': updates, 'delete': deletes}

    @classmethod
    def before_commit(cls, session):
        # Use session.info (a per-session dict) to avoid attaching attributes to the global session
        if not isinstance(session, Session):
            return
        # Initialize/clear changes for this transaction to avoid residual data
        existing = session.info.get('searchable_changes')
        # If existing is not a dict (malformed or leftover), replace it with a fresh dict
        if existing is None or not isinstance(existing, dict):
            session.info['searchable_changes'] = {}

        session.info['searchable_changes'][cls.__name__] = cls._collect_changes(session)

    @classmethod
    def after_commit(cls, session):
        # Defensive checks: ensure session.info has the expected structure
        if not isinstance(session, Session):
            return
        sc = session.info.get('searchable_changes')
        if not sc or not isinstance(sc, dict):
            return
        changes = sc.get(cls.__name__)
        if not changes or not isinstance(changes, dict):
            # Nothing to do
            return

        # Perform atomic index updates using the MockIndex lock in add_to_index
        for obj in changes.get('add', []) + changes.get('update', []) + changes.get('delete', []):
            try:
                add_to_index(cls.__tablename__, obj)
            except Exception:
                # If index update fails, we don't want to leave stale state in session.info
                pass

        # Cleanup per-session stored changes for this class
        try:
            del session.info['searchable_changes'][cls.__name__]
            # If there are no more classes recorded, remove the key entirely
            if not session.info['searchable_changes']:
                del session.info['searchable_changes']
        except Exception:
            # Be defensive: ignore cleanup failures
            pass


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Bind listeners at the Session level so they work with any session scope
@event.listens_for(Session, 'before_commit')
def _session_before_commit(session):
    # For this small demo we only have Post; in larger apps you would iterate mapped classes
    try:
        Post.before_commit(session)
    except Exception:
        pass


@event.listens_for(Session, 'after_commit')
def _session_after_commit(session):
    try:
        Post.after_commit(session)
    except Exception:
        pass
