from datetime import datetime
import threading
from sqlalchemy import event, create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import Session, sessionmaker, scoped_session, declarative_base

# Lightweight DB shim so tests that reference `db.session` and `db.Model`
# keep working without Flask-SQLAlchemy.
engine = None
SessionLocal = None
db = type('DBShim', (), {})()
Base = declarative_base()

def init_db(uri='sqlite:///:memory:'):
    global engine, SessionLocal
    engine = create_engine(uri, connect_args={"check_same_thread": False})
    SessionLocal = scoped_session(sessionmaker(bind=engine))
    db.session = SessionLocal
    db.Model = Base

# Mock search index and lock for atomic updates
INDEX = []
INDEX_LOCK = threading.Lock()


def add_to_index(index_name, obj):
    # Simplified mock index function performed under a lock for atomicity
    with INDEX_LOCK:
        INDEX.append((index_name, obj.id, obj.body))


class SearchableMixin(object):
    @classmethod
    def _collect_changes(cls, session):
        """Collect changes for objects of this class in the session.

        Store the changes in session.info under a per-class key to avoid
        attaching attributes directly to the session object and to be session-safe.
        """
        key = f'searchable_changes_{cls.__name__}'
        # Reinitialize per-transaction to avoid residual data
        session.info[key] = {
            'add': [obj for obj in session.new if isinstance(obj, cls)],
            'update': [obj for obj in session.dirty if isinstance(obj, cls)],
            'delete': [obj for obj in session.deleted if isinstance(obj, cls)]
        }

    @classmethod
    def _get_changes(cls, session):
        key = f'searchable_changes_{cls.__name__}'
        changes = session.info.get(key)
        # Defensive checks: ensure proper structure
        if not isinstance(changes, dict):
            return {'add': [], 'update': [], 'delete': []}
        for k in ('add', 'update', 'delete'):
            if k not in changes or not isinstance(changes[k], list):
                changes[k] = []
        return changes

    @classmethod
    def _clear_changes(cls, session):
        key = f'searchable_changes_{cls.__name__}'
        if key in session.info:
            try:
                del session.info[key]
            except Exception:
                session.info[key] = {'add': [], 'update': [], 'delete': []}


class Post(SearchableMixin, Base):
    __tablename__ = 'post'
    id = Column(Integer, primary_key=True)
    body = Column(String(140))
    timestamp = Column(DateTime, default=datetime.utcnow)


# Bind to SQLAlchemy Session events at the Session class level.
@event.listens_for(Session, 'before_commit')
def session_before_commit(session):
    # For each mapped class that mixes in SearchableMixin, collect changes.
    # In this small app we only have Post, but we use isinstance checks for extensibility.
    try:
        Post._collect_changes(session)
    except Exception:
        # Be defensive; do not let indexing instrumentation break transaction
        Post._clear_changes(session)


@event.listens_for(Session, 'after_commit')
def session_after_commit(session):
    # Atomically process and clear changes. Use lock to ensure index ordering.
    changes = Post._get_changes(session)
    try:
        # Apply adds and updates as index updates
        with INDEX_LOCK:
            for obj in changes.get('add', []):
                add_to_index(Post.__tablename__, obj)
            for obj in changes.get('update', []):
                add_to_index(Post.__tablename__, obj)
            for obj in changes.get('delete', []):
                add_to_index(Post.__tablename__, obj)
    finally:
        # Always clear per-session changes to avoid staleness
        Post._clear_changes(session)


@event.listens_for(Session, 'after_rollback')
def session_after_rollback(session):
    # Ensure no residual state remains after a rollback
    Post._clear_changes(session)
