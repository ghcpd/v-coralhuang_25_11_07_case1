import threading
import time
import pytest
from flask import Flask
from models import db, Post, INDEX, INDEX_LOCK

# Get the Flask app from conftest fixture
@pytest.fixture(scope='session')
def app_for_threads():
    """Provide app for thread-based tests."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    db.init_app(app)
    with app.app_context():
        db.create_all()
    return app


class TestBasicFunctionality:
    """Test basic CRUD operations and indexing."""

    def setup_method(self):
        """Clear INDEX before each test."""
        INDEX.clear()

    def test_create_post_indexed(self):
        """Verify newly created post is added to index."""
        post = Post(body='Test post')
        db.session.add(post)
        db.session.commit()
        
        assert len(INDEX) == 1
        assert INDEX[0][0] == 'post'
        assert INDEX[0][2] == 'Test post'

    def test_update_post_indexed(self):
        """Verify updated post is reflected in index."""
        post = Post(body='Original')
        db.session.add(post)
        db.session.commit()
        
        post.body = 'Updated'
        db.session.commit()
        
        # Should have: create + update
        assert len(INDEX) == 2
        assert INDEX[1][2] == 'Updated'

    def test_delete_post_indexed(self):
        """Verify deleted post triggers index entry."""
        post = Post(body='To delete')
        db.session.add(post)
        db.session.commit()
        post_id = post.id
        
        db.session.delete(post)
        db.session.commit()
        
        # Should have: create + delete
        assert len(INDEX) == 2
        delete_entry = INDEX[1]
        assert delete_entry[0] == 'post'
        assert delete_entry[1] == post_id


class TestConcurrencyAndThreadSafety:
    """Test concurrent commit handling and thread safety."""

    def setup_method(self, app):
        """Clear INDEX and create fresh session."""
        INDEX.clear()

    def test_concurrent_updates_preserve_all_changes(self, app):
        """
        Verify that concurrent commits from multiple threads all appear in index.
        Tests that session.info isolation prevents _changes from being overwritten.
        """
        post = Post(body='Initial')
        db.session.add(post)
        db.session.commit()
        post_id = post.id
        
        results = {'errors': []}

        def update_post(thread_id, new_body):
            try:
                with app.app_context():
                    post = Post.query.get(post_id)
                    post.body = new_body
                    db.session.add(post)
                    db.session.commit()
            except Exception as e:
                results['errors'].append(str(e))

        # Launch concurrent updates
        threads = [
            threading.Thread(target=update_post, args=(1, 'Thread 1 update')),
            threading.Thread(target=update_post, args=(2, 'Thread 2 update')),
            threading.Thread(target=update_post, args=(3, 'Thread 3 update')),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(results['errors']) == 0, f"Errors: {results['errors']}"
        
        # Verify all updates were indexed (create + 3 updates)
        assert len(INDEX) >= 3, f"Expected at least 3 updates, got {len(INDEX)}"
        
        # Verify all thread updates appear in index
        indexed_bodies = [entry[2] for entry in INDEX[1:]]  # Skip initial create
        assert 'Thread 1 update' in indexed_bodies
        assert 'Thread 2 update' in indexed_bodies
        assert 'Thread 3 update' in indexed_bodies

    def test_concurrent_creates_all_indexed(self, app):
        """Verify that concurrent creates all appear in index without loss."""
        results = {'count': 0, 'errors': []}

        def create_post(thread_id):
            try:
                with app.app_context():
                    post = Post(body=f'Post from thread {thread_id}')
                    db.session.add(post)
                    db.session.commit()
                    results['count'] += 1
            except Exception as e:
                results['errors'].append(str(e))

        # Launch concurrent creates
        threads = [threading.Thread(target=create_post, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results['errors']) == 0, f"Errors: {results['errors']}"
        assert results['count'] == 5
        # All 5 creates should be indexed
        assert len(INDEX) == 5, f"Expected 5 indexed creates, got {len(INDEX)}"


class TestDefensiveChecks:
    """Test defensive checks for missing or invalid _changes."""

    def setup_method(self):
        """Clear INDEX."""
        INDEX.clear()

    def test_after_commit_with_missing_changes(self):
        """
        Verify after_commit handles missing searchable_changes gracefully.
        Should not raise AttributeError or KeyError.
        """
        post = Post(body='Test')
        db.session.add(post)
        
        # Manually clear searchable_changes to simulate missing state
        if 'searchable_changes' in db.session.info:
            del db.session.info['searchable_changes']
        
        # Should not raise error even with missing changes
        try:
            db.session.commit()
            # If we reach here, defensive check worked
            assert True
        except (AttributeError, KeyError, TypeError) as e:
            pytest.fail(f"after_commit should handle missing changes: {e}")

    def test_after_commit_with_invalid_changes_type(self):
        """
        Verify after_commit handles non-dict changes gracefully.
        Should perform type check before iteration.
        """
        post = Post(body='Test')
        db.session.add(post)
        
        # Set searchable_changes to invalid type
        db.session.info['searchable_changes'] = "not a dict"
        
        # Should not raise TypeError
        try:
            db.session.commit()
            assert True
        except (TypeError, AttributeError) as e:
            pytest.fail(f"after_commit should handle invalid type: {e}")

    def test_multiple_transactions_isolation(self):
        """
        Verify that _changes from one transaction doesn't leak to next.
        Tests that cleanup prevents residual state.
        """
        # First transaction
        post1 = Post(body='Post 1')
        db.session.add(post1)
        db.session.commit()
        assert len(INDEX) == 1
        
        # Second transaction - should only see its own changes
        post2 = Post(body='Post 2')
        db.session.add(post2)
        db.session.commit()
        
        # Should have exactly 2 index entries (no duplication from residual state)
        assert len(INDEX) == 2, f"Expected 2 entries, got {len(INDEX)}: {INDEX}"


class TestRollbackHandling:
    """Test behavior during transaction rollbacks."""

    def setup_method(self):
        """Clear INDEX."""
        INDEX.clear()

    def test_rollback_clears_residual_state(self):
        """
        Verify that rollback cleans up searchable_changes.
        Prevents rolled-back changes from affecting next transaction.
        """
        post = Post(body='To rollback')
        db.session.add(post)
        db.session.commit()
        initial_index_size = len(INDEX)
        
        # Start transaction and rollback
        post2 = Post(body='Rolled back')
        db.session.add(post2)
        db.session.rollback()
        
        # Verify searchable_changes was cleared
        assert db.session.info.get('searchable_changes', {}) == {}
        
        # Create new post - should work without interference from rollback
        post3 = Post(body='After rollback')
        db.session.add(post3)
        db.session.commit()
        
        # Should have 2 entries (initial + after rollback), not 3
        assert len(INDEX) == initial_index_size + 1

    def test_rollback_no_index_updates(self):
        """
        Verify that rolled-back changes don't appear in index.
        """
        post = Post(body='Committed')
        db.session.add(post)
        db.session.commit()
        index_size_after_commit = len(INDEX)
        
        # Start rollback transaction
        post_rolled_back = Post(body='This will be rolled back')
        db.session.add(post_rolled_back)
        db.session.rollback()
        
        # Index should not have grown
        assert len(INDEX) == index_size_after_commit


class TestAtomicIndexUpdates:
    """Test atomicity of index operations under contention."""

    def setup_method(self):
        """Clear INDEX."""
        INDEX.clear()

    def test_index_lock_prevents_corruption(self, app):
        """
        Verify that INDEX_LOCK ensures consistent index entries.
        Simulates rapid concurrent index updates.
        """
        def add_many_posts(thread_id, count):
            for i in range(count):
                with app.app_context():
                    post = Post(body=f'Post {thread_id}-{i}')
                    db.session.add(post)
                    db.session.commit()

        threads = [
            threading.Thread(target=add_many_posts, args=(1, 5)),
            threading.Thread(target=add_many_posts, args=(2, 5)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 10 entries without loss or duplication
        assert len(INDEX) == 10, f"Expected 10 entries, got {len(INDEX)}"
        
        # All entries should be tuples with correct structure
        for entry in INDEX:
            assert isinstance(entry, tuple)
            assert len(entry) == 3
            assert entry[0] == 'post'
            assert isinstance(entry[1], int)
            assert isinstance(entry[2], str)


class TestSessionIsolation:
    """Test that session.info provides proper isolation."""

    def setup_method(self):
        """Clear INDEX."""
        INDEX.clear()

    def test_session_info_isolation(self):
        """
        Verify that each session has isolated searchable_changes.
        session.info is transaction-scoped, not global.
        """
        # Create in one session
        post1 = Post(body='Post 1')
        db.session.add(post1)
        db.session.commit()
        
        changes_after_first = db.session.info.get('searchable_changes', {})
        
        # Should have been cleared after commit
        assert changes_after_first == {}, "searchable_changes should be empty after commit"
        
        # Second transaction
        post2 = Post(body='Post 2')
        db.session.add(post2)
        db.session.commit()
        
        changes_after_second = db.session.info.get('searchable_changes', {})
        
        # Should again be empty
        assert changes_after_second == {}, "searchable_changes should be empty after second commit"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        """Clear INDEX."""
        INDEX.clear()

    def test_empty_transaction_no_index_update(self):
        """
        Verify that empty transactions (no changes) don't create index entries.
        """
        # Create and commit a post
        post = Post(body='Initial')
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) == 1
        
        # Empty transaction - just commit without changes
        db.session.commit()
        
        # No new index entry should be created
        assert len(INDEX) == 1

    def test_multiple_objects_same_transaction(self):
        """
        Verify that multiple objects in one transaction all appear in index.
        """
        posts = [Post(body=f'Post {i}') for i in range(5)]
        for post in posts:
            db.session.add(post)
        db.session.commit()
        
        # Should have exactly 5 index entries
        assert len(INDEX) == 5

    def test_mixed_operations_same_transaction(self):
        """
        Verify that mixed adds, updates, deletes in one transaction are handled.
        """
        # Create initial posts
        post1 = Post(body='Post 1')
        post2 = Post(body='Post 2')
        db.session.add(post1)
        db.session.add(post2)
        db.session.commit()
        assert len(INDEX) == 2
        
        # Mixed operations in one transaction
        post1.body = 'Updated Post 1'
        post3 = Post(body='Post 3')
        db.session.add(post3)
        db.session.delete(post2)
        db.session.commit()
        
        # Should have create, 2 creates, then update, create, delete = 5 entries
        assert len(INDEX) == 5


def create_post(body):
    """Helper function to create a post."""
    post = Post(body=body)
    db.session.add(post)
    db.session.commit()
    return post


def update_post(post_id, new_body):
    """Helper function to update a post."""
    post = Post.query.get(post_id)
    post.body = new_body
    db.session.add(post)
    db.session.commit()
