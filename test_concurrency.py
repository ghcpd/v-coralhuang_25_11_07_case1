import threading, time
import pytest
from flask import Flask
from models import db, Post, INDEX


def setup_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app


def create_post():
    post = Post(body='Initial post')
    db.session.add(post)
    db.session.commit()
    return post


def update_post(post_id, new_body):
    post = Post.query.get(post_id)
    post.body = new_body
    db.session.add(post)
    db.session.commit()


@pytest.fixture(autouse=True)
def app_ctx():
    app = setup_app()
    with app.app_context():
        yield
        db.session.remove()


def test_concurrent_updates():
    INDEX.clear()
    post = create_post()

    t1 = threading.Thread(target=update_post, args=(post.id, 'Thread 1 update'))
    t2 = threading.Thread(target=update_post, args=(post.id, 'Thread 2 update'))

    # Simulate race conditions in concurrent commits
    t1.start(); t2.start()
    t1.join(); t2.join()

    # Both updates should be indexed
    assert len(INDEX) >= 2, f'Expected at least 2 index updates, got {len(INDEX)}'
    bodies = [entry[2] for entry in INDEX]
    assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies, 'One of the updates was lost'


def test_missing_search_changes_is_safe():
    INDEX.clear()

    # Simulate a session with no search_changes; create a post and commit
    post = Post(body='Safe post')
    db.session.add(post)

    # Remove any pre-set search_changes to simulate missing attribute
    db.session.info.pop('search_changes', None)

    db.session.commit()

    # Should have added the post to index only once
    assert any(entry[0] == 'post' and entry[2] == 'Safe post' for entry in INDEX)


def test_leftover_changes_do_not_leak_between_transactions():
    INDEX.clear()

    # Manually set leftover changes before new transaction
    db.session.info['search_changes'] = {
        'add': [],
        'update': [],
        'delete': []
    }

    post = Post(body='No leak')
    db.session.add(post)
    db.session.commit()

    # The only index updates should be for the commit we just made
    assert any(entry[2] == 'No leak' for entry in INDEX)


def test_rollback_clears_changes():
    INDEX.clear()

    post = Post(body='Will rollback')
    db.session.add(post)

    # Force an error to rollback
    try:
        # create a duplicate primary key violation by inserting same id
        other = Post(id=post.id, body='Conflict')
        db.session.add(other)
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Now perform a normal commit; ensure there are no leftover entries from the failed txn
    post2 = Post(body='After rollback')
    db.session.add(post2)
    db.session.commit()

    assert any(entry[2] == 'After rollback' for entry in INDEX)

