import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

def main():
    results = {
        "test_execution": [],
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        from flask import Flask
        from models import db, Post, INDEX, index_lock
        
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            
            # Test 1: Basic create
            try:
                INDEX.clear()
                post = Post(body='Test post 1')
                db.session.add(post)
                db.session.commit()
                assert len(INDEX) == 1
                results["test_execution"].append({"name": "test_single_thread_create", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_single_thread_create", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 2: Update
            try:
                INDEX.clear()
                post = Post(body='Initial')
                db.session.add(post)
                db.session.commit()
                post.body = 'Updated'
                db.session.add(post)
                db.session.commit()
                assert len(INDEX) >= 2
                results["test_execution"].append({"name": "test_single_thread_update", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_single_thread_update", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 3: Delete
            try:
                INDEX.clear()
                post = Post(body='To delete')
                db.session.add(post)
                db.session.commit()
                db.session.delete(post)
                db.session.commit()
                assert len(INDEX) >= 2
                results["test_execution"].append({"name": "test_single_thread_delete", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_single_thread_delete", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 4: Defensive check
            try:
                INDEX.clear()
                post = Post(body='Test defensive')
                db.session.add(post)
                db.session.commit()
                if 'searchable_changes' in db.session.info:
                    del db.session.info['searchable_changes']
                post.body = 'Updated'
                db.session.add(post)
                db.session.commit()
                results["test_execution"].append({"name": "test_missing_changes_defensive", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_missing_changes_defensive", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 5: Cleanup
            try:
                INDEX.clear()
                post1 = Post(body='Post 1')
                db.session.add(post1)
                db.session.commit()
                assert db.session.info.get('searchable_changes') is None
                post2 = Post(body='Post 2')
                db.session.add(post2)
                db.session.commit()
                assert db.session.info.get('searchable_changes') is None
                results["test_execution"].append({"name": "test_changes_cleanup_after_commit", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_changes_cleanup_after_commit", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 6: Rollback
            try:
                INDEX.clear()
                post = Post(body='Initial')
                db.session.add(post)
                db.session.commit()
                initial_count = len(INDEX)
                post2 = Post(body='Rollback me')
                db.session.add(post2)
                db.session.rollback()
                assert db.session.info.get('searchable_changes') is None
                post3 = Post(body='After rollback')
                db.session.add(post3)
                db.session.commit()
                assert len(INDEX) == initial_count + 1
                results["test_execution"].append({"name": "test_rollback_clears_state", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_rollback_clears_state", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 7: Atomic updates
            try:
                INDEX.clear()
                for i in range(5):
                    post = Post(body=f'Post {i}')
                    db.session.add(post)
                    db.session.commit()
                assert len(INDEX) == 5
                results["test_execution"].append({"name": "test_atomic_index_updates", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_atomic_index_updates", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 8: Type checking
            try:
                INDEX.clear()
                post = Post(body='Type check')
                db.session.add(post)
                db.session.commit()
                db.session.info['searchable_changes'] = "not a dict"
                post.body = 'Updated'
                db.session.add(post)
                db.session.commit()
                results["test_execution"].append({"name": "test_changes_type_checking", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_changes_type_checking", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 9: Event listeners
            try:
                INDEX.clear()
                post = Post(body='Event test')
                db.session.add(post)
                db.session.commit()
                assert len(INDEX) == 1
                post.body = 'Updated'
                db.session.add(post)
                db.session.commit()
                assert len(INDEX) >= 2
                results["test_execution"].append({"name": "test_event_listeners_registered", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_event_listeners_registered", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 10: Multiple transactions
            try:
                INDEX.clear()
                for i in range(3):
                    post = Post(body=f'Transaction {i}')
                    db.session.add(post)
                    db.session.commit()
                assert len(INDEX) == 3
                results["test_execution"].append({"name": "test_multiple_transactions", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_multiple_transactions", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            # Test 11: Exception handling
            try:
                INDEX.clear()
                post = Post(body='Exception test')
                db.session.add(post)
                db.session.commit()
                try:
                    post2 = Post(body='Will fail')
                    db.session.add(post2)
                    raise ValueError("Simulated")
                except ValueError:
                    db.session.rollback()
                assert db.session.info.get('searchable_changes') is None
                post3 = Post(body='After')
                db.session.add(post3)
                db.session.commit()
                assert len(INDEX) == 2
                results["test_execution"].append({"name": "test_exception_handling", "status": "PASSED"})
                results["passed"] += 1
            except Exception as e:
                results["test_execution"].append({"name": "test_exception_handling", "status": "FAILED", "error": str(e)})
                results["failed"] += 1
            
            db.drop_all()
    
    except Exception as e:
        results["errors"].append(str(e))
    
    # Write results
    with open('test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return results

if __name__ == '__main__':
    results = main()
    print(json.dumps(results, indent=2))
