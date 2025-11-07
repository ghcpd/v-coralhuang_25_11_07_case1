from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
from sqlalchemy import event
from sqlalchemy.orm.session import Session

db = SQLAlchemy()
INDEX = []
INDEX_LOCK = threading.Lock()


def add_to_index(index_name, obj):
    # Simplified mock index function (thread-safe)
    with INDEX_LOCK:
        INDEX.append((index_name, obj.id, obj.body))


class SearchableMixin(object):
    @classmethod
    def before_commit(cls, session):
        # Ensure we always start with a fresh search_changes dict per transaction
        changes = {
            'add': [obj for obj in session.new if isinstance(obj, cls)],
            'update': [obj for obj in session.dirty if isinstance(obj, cls)],
            'delete': [obj for obj in session.deleted if isinstance(obj, cls)]
        }
        session.info['search_changes'] = changes

    @classmethod
    def after_commit(cls, session):
        # Defensive checks for existence and type
        changes = session.info.get('search_changes')
        if not isinstance(changes, dict):
            # Nothing to do or malformed; ensure cleanup
            session.info.pop('search_changes', None)
            return

        # Apply index updates atomically per session using the global lock
        with INDEX_LOCK:
            for obj in changes.get('add', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('update', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('delete', []):
                add_to_index(cls.__tablename__, obj)

        # Clean up to prevent stale state
        session.info.pop('search_changes', None)


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Bind events to the SQLAlchemy Session class to ensure all sessions get handlers
@event.listens_for(Session, 'before_commit')
def _search_before_commit(session):
    # Call before_commit on all SearchableMixin subclasses to record session-level changes
    for cls in SearchableMixin.__subclasses__():
        try:
            cls.before_commit(session)
        except Exception:
            # Defensive: do not let one class's error stop others
            pass


@event.listens_for(Session, 'after_commit')
def _search_after_commit(session):
    # Call after_commit on all SearchableMixin subclasses in order
    for cls in SearchableMixin.__subclasses__():
        try:
            cls.after_commit(session)
        except Exception:
            pass
