import threading
import time
import pytest
from models import db, Post, INDEX, INDEX_LOCK


def create_post():
    post = Post(body='Initial post')
    db.session.add(post)
    db.session.commit()
    return post


def update_post(post_id, new_body, delay=0):
    if delay:
        time.sleep(delay)
    post = db.session.query(Post).get(post_id)
    post.body = new_body
    db.session.add(post)
    db.session.commit()


def test_concurrent_updates():
    INDEX.clear()
    post = create_post()

    t1 = threading.Thread(target=update_post, args=(post.id, 'Thread 1 update', 0.01))
    t2 = threading.Thread(target=update_post, args=(post.id, 'Thread 2 update', 0))

    t1.start(); t2.start()
    t1.join(); t2.join()

    # Both updates should be recorded atomically
    bodies = [entry[2] for entry in INDEX]
    assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies


def test_missing_changes_key_is_handled():
    INDEX.clear()
    post = create_post()

    # Manually inject a malformed session.info to simulate missing/invalid _changes
    key = f'searchable_changes_{Post.__name__}'
    db.session.info[key] = 'not-a-dict'

    # Perform an update; the instrumentation should handle the malformed data defensively
    post.body = 'After malformed changes'
    db.session.add(post)
    db.session.commit()

    bodies = [entry[2] for entry in INDEX]
    assert 'After malformed changes' in bodies


def test_rollback_clears_changes():
    INDEX.clear()
    post = create_post()

    # Start a transaction, make a change, then rollback
    db.session.begin()
    post.body = 'Will be rolled back'
    db.session.add(post)
    db.session.rollback()

    # After rollback, ensure no residual index entries and no stale session.info
    key = f'searchable_changes_{Post.__name__}'
    assert key not in db.session.info or db.session.info.get(key) == {'add': [], 'update': [], 'delete': []}


def test_simulated_transaction_isolation():
    INDEX.clear()
    post = create_post()

    # Simulate two separate sessions updating the same post to ensure isolation
    # Create a second scoped session
    sess2 = db.create_scoped_session()
    try:
        p2 = sess2.query(Post).get(post.id)
        p2.body = 'Session2 update'
        sess2.add(p2)
        sess2.commit()

        # Meanwhile original session updates
        post.body = 'Session1 update'
        db.session.add(post)
        db.session.commit()

        bodies = [entry[2] for entry in INDEX]
        assert 'Session1 update' in bodies and 'Session2 update' in bodies
    finally:
        sess2.remove()
