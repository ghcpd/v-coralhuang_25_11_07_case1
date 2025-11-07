import threading
import time
import os
from flask import Flask
from models import db, Post, INDEX

# Setup a Flask app context for SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_db.sqlite'
# Allow SQLite connection across threads in tests
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"connect_args": {"check_same_thread": False}}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Helper fixtures and functions

def setup_module(module):
    """Create DB and tables before running tests in this module."""
    db.init_app(app)
    with app.app_context():
        # Remove existing DB file for reproducibility
        try:
            os.remove('test_db.sqlite')
        except OSError:
            pass
        db.create_all()


def teardown_module(module):
    with app.app_context():
        db.session.remove()
        db.drop_all()
    try:
        os.remove('test_db.sqlite')
    except OSError:
        pass


def create_post():
    with app.app_context():
        post = Post(body='Initial post')
        db.session.add(post)
        db.session.commit()
        return post.id


def update_post(post_id, new_body, pause=0):
    with app.app_context():
        post = Post.query.get(post_id)
        post.body = new_body
        db.session.add(post)
        if pause:
            time.sleep(pause)
        db.session.commit()


def test_concurrent_updates():
    INDEX.clear()
    post_id = create_post()
    # Remove the initial index entry from post creation — we only assert on subsequent updates
    INDEX.clear()

    # Use small sleeps to encourage overlapping commit behavior
    t1 = threading.Thread(target=update_post, args=(post_id, 'Thread 1 update', 0.1))
    t2 = threading.Thread(target=update_post, args=(post_id, 'Thread 2 update', 0))

    t1.start(); t2.start()
    t1.join(); t2.join()

    # With atomic index updates and session-local storage, both changes should be recorded
    assert len(INDEX) == 2, f'Expected 2 index updates, got {len(INDEX)}'
    bodies = [entry[2] for entry in INDEX]
    assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies, 'One of the updates was lost'


def test_missing_or_leftover_changes():
    INDEX.clear()
    with app.app_context():
        # Simulate a stray search_changes arising outside of a commit
        # Create a fake object and place it into session.info incorrectly
        post = Post(body='Leaked')
        db.session.add(post)
        # Manually inject stale search_changes with an incorrect type
        db.session.info['search_changes'] = 'invalid'

        # Commit should not raise and should have a valid dict afterwards
        db.session.commit()
        assert isinstance(db.session.info.get('search_changes', {}), dict) or 'search_changes' not in db.session.info


def test_rollback_clears_state():
    INDEX.clear()
    with app.app_context():
        post = Post(body='Rollback post')
        db.session.add(post)
        db.session.flush()

        # Start a new transaction and force a rollback
        post.body = 'This change will be rolled back'
        db.session.add(post)
        db.session.rollback()

        # After rollback there should be no search_changes in the session info
        assert 'search_changes' not in db.session.info


def test_transaction_isolation_for_concurrent_sessions():
    INDEX.clear()
    post_id = create_post()
    # Remove the initial index entry from post creation — we only assert on subsequent updates
    INDEX.clear()

    # Use two separate app contexts/sessions concurrently
    def worker(name):
        update_post(post_id, f'Update from {name}', pause=0.05)

    threads = [threading.Thread(target=worker, args=(f'T{i}',)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All three updates should appear in the index
    assert len(INDEX) == 3, f'Expected 3 index updates, got {len(INDEX)}'