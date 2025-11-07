import threading
import time
import json
from flask import Flask
from models import db, Post, INDEX


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def setup_db(app):
    with app.app_context():
        db.create_all()


def teardown_db(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def create_post(body='Initial post'):
    post = Post(body=body)
    db.session.add(post)
    db.session.commit()
    return post


def update_post(post_id, new_body, delay=0, app=None):
    # Each thread must push an app context for Flask-SQLAlchemy to work
    if delay:
        time.sleep(delay)
    if app is not None:
        with app.app_context():
            post = Post.query.get(post_id)
            post.body = new_body
            db.session.add(post)
            db.session.commit()
    else:
        post = Post.query.get(post_id)
        post.body = new_body
        db.session.add(post)
        db.session.commit()


def test_concurrent_updates():
    app = create_app()
    setup_db(app)
    with app.app_context():
        INDEX.clear()
        post = create_post()

        t1 = threading.Thread(target=update_post, args=(post.id, 'Thread 1 update', 0.1, app))
        t2 = threading.Thread(target=update_post, args=(post.id, 'Thread 2 update', 0, app))

        t1.start(); t2.start()
        t1.join(); t2.join()

        entries = INDEX.all()
        bodies = [entry[2] for entry in entries]
        assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies, f'Expected both updates in index, got {bodies}'

    teardown_db(app)


def test_missing_and_leftover_changes():
    app = create_app()
    setup_db(app)
    with app.app_context():
        INDEX.clear()

        # Simulate manual leftover state in session.info
        # Start a transaction but do not commit; manually inject leftover
        post = Post(body='Transient')
        db.session.add(post)
        db.session.flush()
        # Inject a malformed searchable_changes
        db.session.info['searchable_changes'] = 'not-a-dict'
        # Now rollback and ensure after commit handlers don't break
        db.session.rollback()

        # Now create a proper post and commit; handlers should work normally
        p2 = create_post('Persistent')
        entries = INDEX.all()
        bodies = [e[2] for e in entries]
        assert 'Persistent' in bodies, 'Expected Persistent post to be indexed'

    teardown_db(app)


def test_rollback_and_residual_state():
    app = create_app()
    setup_db(app)
    with app.app_context():
        INDEX.clear()
        # Start a transaction and force an exception to cause rollback
        post = Post(body='WillRollback')
        db.session.add(post)
        try:
            # Simulate failure during commit by raising inside a flush hook
            raise RuntimeError('Simulated failure')
        except Exception:
            db.session.rollback()

        # After rollback, session.info should not keep leftover for Post
        assert 'searchable_changes' not in db.session.info or db.session.info.get('searchable_changes') == {}, 'Residual searchable_changes after rollback'

    teardown_db(app)


if __name__ == '__main__':
    # Run tests manually and print simple results
    results = {'passed': [], 'failed': []}
    for fn in [test_concurrent_updates, test_missing_and_leftover_changes, test_rollback_and_residual_state]:
        name = fn.__name__
        try:
            fn()
            results['passed'].append(name)
            print(f'PASSED: {name}')
        except AssertionError as e:
            results['failed'].append({'name': name, 'error': str(e)})
            print(f'FAILED: {name} - {e}')
    print(json.dumps(results, indent=2))
