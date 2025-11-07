import threading
import time
from models import db, Post, INDEX, create_app


def setup_db():
    # Use a file-based sqlite DB to allow threads to share the DB
    app = create_app('sqlite:///test_db.sqlite')
    return app


def create_post():
    post = Post(body='Initial post')
    db.session.add(post)
    db.session.commit()
    return post


def update_post(post_id, new_body, delay=0, app=None):
    # Small optional delay to increase chance of overlap
    if delay:
        time.sleep(delay)
    # Each thread must push its own app context for Flask-SQLAlchemy
    if app is None:
        raise RuntimeError('app must be provided to update_post')
    with app.app_context():
        post = Post.query.get(post_id)
        post.body = new_body
        db.session.add(post)
        db.session.commit()


def test_concurrent_updates():
    INDEX.clear()
    app = setup_db()

    with app.app_context():
        post = create_post()

        t1 = threading.Thread(target=update_post, args=(post.id, 'Thread 1 update', 0.01, app))
        t2 = threading.Thread(target=update_post, args=(post.id, 'Thread 2 update', 0, app))

        t1.start(); t2.start()
        t1.join(); t2.join()

        # Both update events should be recorded in the index
        bodies = [entry[2] for entry in INDEX]
        assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies, f'Index missing updates: {bodies}'


def test_missing_or_stale_changes():
    # Simulate a session that never had searchable_changes set or it's malformed
    app = setup_db()

    with app.app_context():
        INDEX.clear()

        # Directly manipulate session.info to simulate stale state
        db.session.info['searchable_changes'] = 'not-a-dict'

        p = Post(body='Will be added')
        db.session.add(p)
        # commit should not raise and should handle malformed session.info
        db.session.commit()

        # The add should have been indexed despite earlier malformed state
        bodies = [entry[2] for entry in INDEX]
        assert 'Will be added' in bodies


def test_residual_state_is_cleared_between_transactions():
    app = setup_db()

    with app.app_context():
        INDEX.clear()

        a = Post(body='First')
        db.session.add(a)
        db.session.commit()

        # Manually ensure session.info is empty after commit
        assert db.session.info.get('searchable_changes') in (None, {})

        b = Post(body='Second')
        db.session.add(b)
        db.session.commit()

        bodies = [entry[2] for entry in INDEX]
        assert 'First' in bodies and 'Second' in bodies
