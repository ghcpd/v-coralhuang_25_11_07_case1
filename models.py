from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading

db = SQLAlchemy()
INDEX = []
index_lock = threading.Lock()

def add_to_index(index_name, obj):
    """Thread-safe index update with atomic lock"""
    with index_lock:
        INDEX.append((index_name, obj.id, obj.body))

class SearchableMixin(object):
    @classmethod
    def before_commit(cls, session):
        """
        Fix 3 & 4: Use session.info (session-local, not shared globally)
        Fix 2: Reinitialize _changes at the start of each transaction
        Fix 1: Initialize with proper type checking (dict)
        """
        # Initialize session.info if not present (session-safe storage)
        if 'searchable_changes' not in session.info:
            session.info['searchable_changes'] = {}
        
        # Reinitialize _changes at start of transaction (Fix 2)
        session.info['searchable_changes'] = {
            'add': [obj for obj in session.new if isinstance(obj, cls)],
            'update': [obj for obj in session.dirty if isinstance(obj, cls)],
            'delete': [obj for obj in session.deleted if isinstance(obj, cls)]
        }

    @classmethod
    def after_commit(cls, session):
        """
        Fix 1: Defensive check for existence and type of _changes
        Fix 5: Atomic index updates via lock
        Fix 2: Cleanup after commit
        """
        # Fix 1: Defensive check for existence and type
        if 'searchable_changes' not in session.info:
            return
        
        changes = session.info.get('searchable_changes')
        if not isinstance(changes, dict):
            return
        
        # Fix 5: Atomic index updates
        with index_lock:
            for obj in changes.get('add', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('update', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('delete', []):
                add_to_index(cls.__tablename__, obj)
        
        # Fix 2: Cleanup after commit
        session.info['searchable_changes'] = None

    @classmethod
    def after_rollback(cls, session):
        """
        Handle rollback scenario: clear stale _changes
        """
        if 'searchable_changes' in session.info:
            session.info['searchable_changes'] = None

class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Fix 6: Use SQLAlchemy's recommended event.listens_for pattern
# This applies to all Session instances, not just db.session
from sqlalchemy.orm import Session
from sqlalchemy import event

@event.listens_for(Session, 'before_commit')
def receive_before_commit(session):
    """Register before_commit at Session level"""
    Post.before_commit(session)

@event.listens_for(Session, 'after_commit')
def receive_after_commit(session):
    """Register after_commit at Session level"""
    Post.after_commit(session)

@event.listens_for(Session, 'after_rollback')
def receive_after_rollback(session):
    """Handle rollback to clear stale data"""
    Post.after_rollback(session)
