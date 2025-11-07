#!/usr/bin/env python3
"""Direct test execution"""

import sys
import os

# Add to path
sys.path.insert(0, os.getcwd())

print("=" * 70)
print("TESTING FIXES - DIRECT EXECUTION")
print("=" * 70)

try:
    from flask import Flask
    from models import db, Post, INDEX, index_lock
    print("✓ Imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Create app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

passed = 0
failed = 0

def run_test(name, test_func):
    global passed, failed
    try:
        test_func()
        print(f"✓ {name}")
        passed += 1
    except AssertionError as e:
        print(f"✗ {name}: {e}")
        failed += 1
    except Exception as e:
        print(f"✗ {name}: {type(e).__name__}: {e}")
        failed += 1

with app.app_context():
    db.create_all()
    
    # Test 1
    def test1():
        INDEX.clear()
        post = Post(body='Test post 1')
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) == 1, f"Expected 1, got {len(INDEX)}"
        assert INDEX[0][2] == 'Test post 1'
    
    run_test("test_single_thread_create", test1)
    
    # Test 2
    def test2():
        INDEX.clear()
        post = Post(body='Initial')
        db.session.add(post)
        db.session.commit()
        post.body = 'Updated'
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) >= 2, f"Expected >= 2, got {len(INDEX)}"
        bodies = [entry[2] for entry in INDEX]
        assert 'Initial' in bodies
        assert 'Updated' in bodies
    
    run_test("test_single_thread_update", test2)
    
    # Test 3
    def test3():
        INDEX.clear()
        post = Post(body='To delete')
        db.session.add(post)
        db.session.commit()
        db.session.delete(post)
        db.session.commit()
        assert len(INDEX) >= 2, f"Expected >= 2, got {len(INDEX)}"
    
    run_test("test_single_thread_delete", test3)
    
    # Test 4 - Defensive check
    def test4():
        INDEX.clear()
        post = Post(body='Test defensive')
        db.session.add(post)
        db.session.commit()
        
        if 'searchable_changes' in db.session.info:
            del db.session.info['searchable_changes']
        
        post.body = 'Updated after removal'
        db.session.add(post)
        db.session.commit()
    
    run_test("test_missing_changes_defensive", test4)
    
    # Test 5 - Cleanup
    def test5():
        INDEX.clear()
        post1 = Post(body='Post 1')
        db.session.add(post1)
        db.session.commit()
        assert db.session.info.get('searchable_changes') is None, "Not cleaned up"
        
        post2 = Post(body='Post 2')
        db.session.add(post2)
        db.session.commit()
        assert db.session.info.get('searchable_changes') is None, "Not cleaned up after 2nd"
    
    run_test("test_changes_cleanup_after_commit", test5)
    
    # Test 6 - Rollback
    def test6():
        INDEX.clear()
        post = Post(body='Initial')
        db.session.add(post)
        db.session.commit()
        initial_count = len(INDEX)
        
        post2 = Post(body='Rollback me')
        db.session.add(post2)
        db.session.rollback()
        assert db.session.info.get('searchable_changes') is None, "Not cleared on rollback"
        
        post3 = Post(body='After rollback')
        db.session.add(post3)
        db.session.commit()
        assert len(INDEX) == initial_count + 1, f"Expected {initial_count + 1}, got {len(INDEX)}"
    
    run_test("test_rollback_clears_state", test6)
    
    # Test 7 - Session isolation
    def test7():
        INDEX.clear()
        post = Post(body='Shared test')
        db.session.add(post)
        db.session.commit()
        post_id = post.id
        
        session1 = db.session()
        session2 = db.session()
        
        try:
            p1 = session1.query(Post).get(post_id)
            p1.body = 'Updated by session1'
            session1.add(p1)
            session1.commit()
            count_after_s1 = len(INDEX)
            
            p2 = session2.query(Post).get(post_id)
            p2.body = 'Updated by session2'
            session2.add(p2)
            session2.commit()
            count_after_s2 = len(INDEX)
            
            assert count_after_s2 > count_after_s1
            bodies = [entry[2] for entry in INDEX]
            assert 'Updated by session1' in bodies
            assert 'Updated by session2' in bodies
        finally:
            session1.close()
            session2.close()
    
    run_test("test_session_isolation", test7)
    
    # Test 8 - Atomic updates
    def test8():
        INDEX.clear()
        for i in range(5):
            post = Post(body=f'Post {i}')
            db.session.add(post)
            db.session.commit()
        assert len(INDEX) == 5
    
    run_test("test_atomic_index_updates", test8)
    
    # Test 9 - Type checking
    def test9():
        INDEX.clear()
        post = Post(body='Type check test')
        db.session.add(post)
        db.session.commit()
        
        db.session.info['searchable_changes'] = "not a dict"
        post.body = 'Updated'
        db.session.add(post)
        db.session.commit()
    
    run_test("test_changes_type_checking", test9)
    
    # Test 10 - Event listeners
    def test10():
        INDEX.clear()
        post = Post(body='Event listener test')
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) == 1
        
        post.body = 'Updated'
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) >= 2
    
    run_test("test_event_listeners_registered", test10)
    
    # Test 11 - Multiple transactions
    def test11():
        INDEX.clear()
        for i in range(3):
            post = Post(body=f'Transaction {i}')
            db.session.add(post)
            db.session.commit()
        assert len(INDEX) == 3
    
    run_test("test_multiple_transactions", test11)
    
    # Test 12 - Exception handling
    def test12():
        INDEX.clear()
        post = Post(body='Exception test')
        db.session.add(post)
        db.session.commit()
        
        try:
            post2 = Post(body='Will fail')
            db.session.add(post2)
            raise ValueError("Simulated error")
        except ValueError:
            db.session.rollback()
        
        assert db.session.info.get('searchable_changes') is None
        
        post3 = Post(body='After exception')
        db.session.add(post3)
        db.session.commit()
        assert len(INDEX) == 2
    
    run_test("test_exception_handling", test12)
    
    db.drop_all()

print("\n" + "=" * 70)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 70)

sys.exit(0 if failed == 0 else 1)
