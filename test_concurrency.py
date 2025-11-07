import os
import threading
import time
import json
import pytest
from models import db, Post, INDEX
from flask import Flask

DB_FILE = 'test.db'


@pytest.fixture(scope='module')
def app():
    # Setup Flask app and SQLite test DB
    if os.path.exists(DB_FILE):
        os.unlink(DB_FILE)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_FILE}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    if os.path.exists(DB_FILE):
        os.unlink(DB_FILE)


def create_post(app):
    with app.app_context():
        post = Post(body='Initial post')
        db.session.add(post)
        db.session.commit()
        return post.id


def update_post(app, post_id, new_body, delay=0):
    # Each thread needs an app context to use flask_sqlalchemy's session
    with app.app_context():
        post = Post.query.get(post_id)
        if delay:
            time.sleep(delay)
        post.body = new_body
        db.session.add(post)
        db.session.commit()


def test_concurrent_updates(app):
    INDEX.clear()
    post_id = create_post(app)

    # Clear index after creation to test only concurrent updates
    INDEX.clear()

    t1 = threading.Thread(target=update_post, args=(app, post_id, 'Thread 1 update', 0.1))
    t2 = threading.Thread(target=update_post, args=(app, post_id, 'Thread 2 update', 0))

    t1.start(); t2.start()
    t1.join(); t2.join()

    # Both updates should be recorded in the index
    assert len(INDEX) == 2, f'Expected 2 index updates, got {len(INDEX)}'
    bodies = [entry[2] for entry in INDEX]
    assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies, 'One of the updates was lost'


def test_rollback_and_cleanup(app):
    INDEX.clear()
    # Create a post then attempt an update that is rolled back
    post_id = create_post(app)

    with app.app_context():
        # Start a transaction, modify and rollback
        post_to_modify = Post.query.get(post_id)
        post_to_modify.body = 'Rolled back update'
        db.session.add(post_to_modify)
        db.session.rollback()  # do not commit

        # Now commit a real update
        post_to_modify.body = 'Committed update'
        db.session.add(post_to_modify)
        db.session.commit()

    # Only the committed update should be in the index
    bodies = [entry[2] for entry in INDEX]
    assert 'Committed update' in bodies
    assert 'Rolled back update' not in bodies


def test_leftover_changes_cleared_and_defensive_handling(app):
    INDEX.clear()
    post_id = create_post(app)

    with app.app_context():
        # Simulate a corrupted leftover in session.info
        db.session.info['searchable_changes'] = 'malformed'

        # Do a commit that should reinitialize the structure
        p = Post.query.get(post_id)
        p.body = 'Valid update after malformed'
        db.session.add(p)
        db.session.commit()

    bodies = [entry[2] for entry in INDEX]
    assert 'Valid update after malformed' in bodies


def test_concurrent_creation_isolated_indexing(app):
    INDEX.clear()

    def create_with_body(app, text):
        with app.app_context():
            p = Post(body=text)
            db.session.add(p)
            db.session.commit()

    threads = [threading.Thread(target=create_with_body, args=(app, f'Post {i}')) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All created posts should appear in the index once
    bodies = [entry[2] for entry in INDEX]
    for i in range(5):
        assert f'Post {i}' in bodies

