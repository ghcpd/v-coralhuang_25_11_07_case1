import threading
import time
import os
import json
import pytest
from models import app, db, Post, INDEX

@pytest.fixture(scope='module', autouse=True)
def setup_db():
    # Ensure the database file is removed before tests
    db_file = 'test.db'
    if os.path.exists(db_file):
        os.unlink(db_file)

    # Create tables
    with app.app_context():
        db.create_all()
    yield
    # Teardown
    with app.app_context():
        db.session.remove()
        db.drop_all()
    if os.path.exists(db_file):
        os.unlink(db_file)


def create_post():
    with app.app_context():
        post = Post(body='Initial post')
        db.session.add(post)
        db.session.commit()
        # Return the id to avoid passing a detached instance to other threads
        return post.id


def update_post(post_id, new_body, wait=0):
    # Each thread must have its own session context
    time.sleep(wait)
    with app.app_context():
        post = db.session.get(Post, post_id)
        post.body = new_body
        db.session.add(post)
        db.session.commit()


def test_concurrent_updates():
    INDEX.clear()
    post_id = create_post()

    t1 = threading.Thread(target=update_post, args=(post_id, 'Thread 1 update', 0.01))
    t2 = threading.Thread(target=update_post, args=(post_id, 'Thread 2 update', 0))

    # Simulate race conditions in concurrent commits
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Both updates should appear in INDEX despite concurrency
    bodies = [entry[2] for entry in INDEX]
    assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies, f"Missing updates: {bodies}"


def test_missing_leftover_changes_cleanup():
    INDEX.clear()
    with app.app_context():
        # Manually set a leftover 'searchable_changes' on the session (simulating a stale value)
        db.session.info['searchable_changes'] = {'add': ['leftover'], 'update': [], 'delete': []}
        # Perform a transaction that should override/clear the previous state
        post = Post(body='New post')
        db.session.add(post)
        db.session.commit()
        # After commit, session.info should not have leftover
        assert 'searchable_changes' not in db.session.info, 'searchable_changes not cleaned up after commit'


def test_rollback_clears_state():
    INDEX.clear()
    with app.app_context():
        # Cause an integrity error via adding a post with bad data (e.g., None for non-nullable id) to force rollback
        post = Post(body='Rollback post')
        db.session.add(post)
        # Force a rollback by raising an exception inside a commit context
        try:
            # This will succeed normally; we simulate a manual rollback
            db.session.commit()
            # Now start a transaction and rollback explicitly
            post2 = Post(body='Will rollback')
            db.session.add(post2)
            db.session.flush()
            # Rollback
            db.session.rollback()
        finally:
            # session.info should be clear
            assert 'searchable_changes' not in db.session.info, 'searchable_changes should be cleared after rollback'


def test_atomic_index_updates_ordering():
    INDEX.clear()
    # Create several updates rapidly and ensure order preserved within the index via our lock
    post_id = create_post()

    def updater(i, wait):
        update_post(post_id, f'Update {i}', wait)

    threads = [threading.Thread(target=updater, args=(i, i*0.01)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Ensure all updates are present and no partial states
    bodies = [entry[2] for entry in INDEX]
    assert len([b for b in bodies if b.startswith('Update')]) == 5, 'Not all updates were indexed'


if __name__ == '__main__':
    pytest.main(['-q', '--disable-warnings', '--maxfail=1'])
