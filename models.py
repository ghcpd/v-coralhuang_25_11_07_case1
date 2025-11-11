from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import threading
from sqlalchemy import event
from sqlalchemy.orm import Session

db = SQLAlchemy()
INDEX = []
# Lock for atomic index updates (Problem 4 fix)
_index_lock = threading.Lock()

# Registry to track SearchableMixin subclasses (Problem 6 fix)
_searchable_classes = set()

def add_to_index(index_name, obj):
    # Fixed: atomic index updates using lock
    with _index_lock:
        INDEX.append((index_name, obj.id, obj.body))

class SearchableMixin(object):
    """Mixin class for models that need search index integration."""
    
    def __init_subclass__(cls, **kwargs):
        """Register subclasses when they are defined."""
        super().__init_subclass__(**kwargs)
        if cls != SearchableMixin:
            _searchable_classes.add(cls)
    
    @classmethod
    def before_commit(cls, session):
        # Fixed Problem 2: Clear/reset _changes at start of each transaction
        # Fixed Problem 3: Use session.info instead of direct attribute (thread-safe)
        if not hasattr(session, 'info'):
            session.info = {}
        
        # Initialize or clear _changes for this transaction
        # Handle case where _changes might be wrong type (defensive programming)
        if '_changes' not in session.info or not isinstance(session.info['_changes'], dict):
            session.info['_changes'] = {}
        
        # Reset changes for this class type
        if cls.__name__ not in session.info['_changes'] or not isinstance(session.info['_changes'][cls.__name__], dict):
            session.info['_changes'][cls.__name__] = {
                'add': [],
                'update': [],
                'delete': []
            }
        
        # Clear previous changes and populate with current transaction state
        session.info['_changes'][cls.__name__] = {
            'add': [obj for obj in session.new if isinstance(obj, cls)],
            'update': [obj for obj in session.dirty if isinstance(obj, cls)],
            'delete': [obj for obj in session.deleted if isinstance(obj, cls)]
        }

    @classmethod
    def after_commit(cls, session):
        # Fixed Problem 1: Defensive check for existence and type of _changes
        if not hasattr(session, 'info') or not isinstance(session.info, dict):
            return
        
        if '_changes' not in session.info:
            return
        
        if cls.__name__ not in session.info['_changes']:
            return
        
        changes = session.info['_changes'][cls.__name__]
        
        # Additional type check
        if not isinstance(changes, dict):
            return
        
        # Process changes atomically
        try:
            for obj in changes.get('add', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('update', []):
                add_to_index(cls.__tablename__, obj)
            for obj in changes.get('delete', []):
                add_to_index(cls.__tablename__, obj)
        except Exception as e:
            # Log error but don't fail the transaction
            print(f"Error updating index for {cls.__name__}: {e}")
        finally:
            # Fixed Problem 2: Cleanup after commit
            if cls.__name__ in session.info.get('_changes', {}):
                del session.info['_changes'][cls.__name__]

class Post(SearchableMixin, db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Fixed Problem 6: Use SQLAlchemy's recommended event.listens_for pattern
# This ensures events are bound to Session class, not a specific instance
@event.listens_for(Session, 'before_commit')
def receive_before_commit(session):
    """Handle before_commit for all SearchableMixin subclasses"""
    for cls in _searchable_classes:
        cls.before_commit(session)

@event.listens_for(Session, 'after_commit')
def receive_after_commit(session):
    """Handle after_commit for all SearchableMixin subclasses"""
    for cls in _searchable_classes:
        cls.after_commit(session)

