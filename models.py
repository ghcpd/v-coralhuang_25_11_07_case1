from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import Session
import threading

db = SQLAlchemy()

# In-memory mock index and a lock to make updates atomic in this demo
INDEX = []
_index_lock = threading.Lock()


def add_to_index(index_name, obj):
    # Simulated atomic index update
    with _index_lock:
        INDEX.append((index_name, obj.id, obj.body))


class SearchableMixin(object):
    """
    Fixed SearchableMixin that stores per-session changes in `session.info`
    and uses Session-level event listeners for before/after commit.
    """

    @staticmethod
    def _collect_changes(session):
        # Initialize fresh per-transaction storage to avoid stale data
        session.info['searchable_changes'] = {}

        for obj in session.new:
            if isinstance(obj, SearchableMixin):
                tab = getattr(obj, '__tablename__', None) or obj.__class__.__name__
                session.info['searchable_changes'].setdefault(tab, {'add': [], 'update': [], 'delete': []})
                session.info['searchable_changes'][tab]['add'].append(obj)

        for obj in session.dirty:
            if isinstance(obj, SearchableMixin):
                tab = getattr(obj, '__tablename__', None) or obj.__class__.__name__
                session.info['searchable_changes'].setdefault(tab, {'add': [], 'update': [], 'delete': []})
                session.info['searchable_changes'][tab]['update'].append(obj)

        for obj in session.deleted:
            if isinstance(obj, SearchableMixin):
                tab = getattr(obj, '__tablename__', None) or obj.__class__.__name__
                session.info['searchable_changes'].setdefault(tab, {'add': [], 'update': [], 'delete': []})
                session.info['searchable_changes'][tab]['delete'].append(obj)


@event.listens_for(Session, 'before_commit')
def session_before_commit(session):
    # Clear/initialize session-local storage to ensure isolation
    try:
        SearchableMixin._collect_changes(session)
    except Exception:
        # Defensive: ensure we never leave session.info in a bad state
        session.info['searchable_changes'] = {}


@event.listens_for(Session, 'after_commit')
def session_after_commit(session):
    # Defensive checks for existence and correct type
    changes = session.info.get('searchable_changes')
    if not isinstance(changes, dict):
        # If stale or malformed, reset and exit gracefully
        session.info['searchable_changes'] = {}
        return

    # Apply index updates with an atomic lock to simulate transactional ordering
    for tablename, groups in changes.items():
        if not isinstance(groups, dict):
            continue
        for action in ('add', 'update', 'delete'):
            objs = groups.get(action) or []
            for obj in objs:
                try:
                    add_to_index(tablename, obj)
                except Exception:
                    # In production, you'd log and/or enqueue a retry
                    pass

    # Cleanup to avoid leaving residual state
    session.info['searchable_changes'] = {}


class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


def create_app(database_uri='sqlite:///:memory:'):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app
