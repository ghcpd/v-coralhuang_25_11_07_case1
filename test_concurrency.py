import threading
import time
import pytest
from models import db, Post, INDEX, index_lock
from flask import Flask

# Test fixtures
@pytest.fixture
def app():
    """Create Flask app with SQLite in-memory database"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def clear_index():
    """Clear the index before each test"""
    with index_lock:
        INDEX.clear()
    yield
    with index_lock:
        INDEX.clear()

# Test 1: Basic functionality - single thread
def test_single_thread_create(app, clear_index):
    """Test basic create operation in single thread"""
    with app.app_context():
        post = Post(body='Test post 1')
        db.session.add(post)
        db.session.commit()
        
        assert len(INDEX) == 1
        assert INDEX[0][2] == 'Test post 1'

def test_single_thread_update(app, clear_index):
    """Test basic update operation in single thread"""
    with app.app_context():
        post = Post(body='Initial')
        db.session.add(post)
        db.session.commit()
        
        post.body = 'Updated'
        db.session.add(post)
        db.session.commit()
        
        # Should have add + update = 2 entries
        assert len(INDEX) >= 2
        bodies = [entry[2] for entry in INDEX]
        assert 'Initial' in bodies
        assert 'Updated' in bodies

def test_single_thread_delete(app, clear_index):
    """Test basic delete operation in single thread"""
    with app.app_context():
        post = Post(body='To delete')
        db.session.add(post)
        db.session.commit()
        
        db.session.delete(post)
        db.session.commit()
        
        # Should have add + delete = 2 entries
        assert len(INDEX) >= 2

# Test 2: Concurrent updates without race conditions
def test_concurrent_updates(app, clear_index):
    """Test concurrent updates from multiple threads"""
    with app.app_context():
        post = Post(body='Initial post')
        db.session.add(post)
        db.session.commit()
        post_id = post.id
        
        def update_post(new_body):
            # Create new session for each thread
            session = db.session()
            post = session.query(Post).get(post_id)
            if post:
                post.body = new_body
                session.add(post)
                session.commit()
            session.close()
        
        INDEX.clear()
        
        t1 = threading.Thread(target=update_post, args=('Thread 1 update',))
        t2 = threading.Thread(target=update_post, args=('Thread 2 update',))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Both updates should be indexed
        assert len(INDEX) >= 2
        bodies = [entry[2] for entry in INDEX]
        assert 'Thread 1 update' in bodies and 'Thread 2 update' in bodies

# Test 3: Missing _changes check - defensive coding
def test_missing_changes_defensive(app, clear_index):
    """
    Test that after_commit handles missing _changes gracefully (Fix 1)
    """
    with app.app_context():
        post = Post(body='Test defensive')
        db.session.add(post)
        db.session.commit()
        
        # Manually remove searchable_changes to simulate edge case
        if 'searchable_changes' in db.session.info:
            del db.session.info['searchable_changes']
        
        # This should not raise an error
        post.body = 'Updated after removal'
        db.session.add(post)
        db.session.commit()
        
        # Should still work without crashing
        assert True

# Test 4: Stale _changes cleanup
def test_changes_cleanup_after_commit(app, clear_index):
    """
    Test that _changes is properly cleaned up after commit (Fix 2)
    """
    with app.app_context():
        post1 = Post(body='Post 1')
        db.session.add(post1)
        db.session.commit()
        
        # Check that searchable_changes is cleaned
        assert db.session.info.get('searchable_changes') is None
        
        post2 = Post(body='Post 2')
        db.session.add(post2)
        db.session.commit()
        
        # Cleanup should prevent stale data
        assert db.session.info.get('searchable_changes') is None

# Test 5: Rollback clears residual state
def test_rollback_clears_state(app, clear_index):
    """
    Test that rollback properly clears stale _changes (Fix 2)
    """
    with app.app_context():
        post = Post(body='Initial')
        db.session.add(post)
        db.session.commit()
        
        initial_count = len(INDEX)
        
        # Start transaction but rollback
        post2 = Post(body='Rollback me')
        db.session.add(post2)
        db.session.rollback()
        
        # After rollback, searchable_changes should be cleared
        assert db.session.info.get('searchable_changes') is None
        
        # New transaction should work fine
        post3 = Post(body='After rollback')
        db.session.add(post3)
        db.session.commit()
        
        # Should have exactly 2 more entries (initial + post3)
        assert len(INDEX) == initial_count + 1

# Test 6: Session isolation (Fix 3 & 4)
def test_session_isolation(app, clear_index):
    """
    Test that _changes is isolated per session, not shared (Fix 3)
    """
    with app.app_context():
        # Create initial post
        post = Post(body='Shared test')
        db.session.add(post)
        db.session.commit()
        post_id = post.id
        
        INDEX.clear()
        
        # Use separate sessions
        session1 = db.session()
        session2 = db.session()
        
        try:
            # Update in session1
            p1 = session1.query(Post).get(post_id)
            p1.body = 'Updated by session1'
            session1.add(p1)
            session1.commit()
            
            count_after_s1 = len(INDEX)
            
            # Update in session2 (should not interfere)
            p2 = session2.query(Post).get(post_id)
            p2.body = 'Updated by session2'
            session2.add(p2)
            session2.commit()
            
            count_after_s2 = len(INDEX)
            
            # Both updates should be in index
            assert count_after_s2 > count_after_s1
            bodies = [entry[2] for entry in INDEX]
            assert 'Updated by session1' in bodies
            assert 'Updated by session2' in bodies
        finally:
            session1.close()
            session2.close()

# Test 7: Atomic index updates with lock (Fix 5)
def test_atomic_index_updates(app, clear_index):
    """
    Test that index updates are atomic via lock (Fix 5)
    """
    with app.app_context():
        updates_count = 10
        
        def create_posts(num):
            for i in range(num):
                post = Post(body=f'Post {i}')
                db.session.add(post)
                db.session.commit()
        
        t1 = threading.Thread(target=create_posts, args=(5,))
        t2 = threading.Thread(target=create_posts, args=(5,))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # All 10 should be indexed
        assert len(INDEX) == updates_count

# Test 8: Type checking for _changes (Fix 1)
def test_changes_type_checking(app, clear_index):
    """
    Test that _changes type is validated (Fix 1)
    """
    with app.app_context():
        post = Post(body='Type check test')
        db.session.add(post)
        db.session.commit()
        
        # Corrupt the type
        db.session.info['searchable_changes'] = "not a dict"
        
        # This should handle gracefully
        post.body = 'Updated'
        db.session.add(post)
        db.session.commit()
        
        # Should not crash
        assert True

# Test 9: Concurrent exception handling
def test_concurrent_with_exceptions(app, clear_index):
    """
    Test that concurrent operations handle exceptions properly
    """
    with app.app_context():
        post = Post(body='Exception test')
        db.session.add(post)
        db.session.commit()
        post_id = post.id
        
        def update_or_fail(should_fail, body):
            session = db.session()
            try:
                post = session.query(Post).get(post_id)
                if should_fail:
                    # Simulate some processing
                    raise ValueError("Simulated error")
                post.body = body
                session.add(post)
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()
        
        t1 = threading.Thread(target=update_or_fail, args=(True, 'Should fail'))
        t2 = threading.Thread(target=update_or_fail, args=(False, 'Should succeed'))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # At least one should have succeeded
        assert len(INDEX) >= 1

# Test 10: Event listener registration (Fix 6)
def test_event_listeners_registered(app, clear_index):
    """
    Test that event listeners are properly registered at Session level (Fix 6)
    """
    with app.app_context():
        # Create and commit
        post = Post(body='Event listener test')
        db.session.add(post)
        db.session.commit()
        
        # Check that index was updated (proving event was triggered)
        assert len(INDEX) == 1
        
        # Update
        post.body = 'Updated'
        db.session.add(post)
        db.session.commit()
        
        # Check that update was indexed
        assert len(INDEX) >= 2

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
