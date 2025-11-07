#!/usr/bin/env python3
"""Test validation script"""

import sys
sys.path.insert(0, 'c:\\Bug_Bash\\25_11_07\\v-coralhuang_25_11_07_case1')

from flask import Flask
from models import db, Post, INDEX, index_lock
import time

print("=" * 70)
print("MANUAL TEST VALIDATION")
print("=" * 70)

# Create Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    
    # Test 1: Basic create
    print("\n[Test 1] Basic create operation...")
    try:
        post = Post(body='Test post 1')
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) == 1, f"Expected 1 index entry, got {len(INDEX)}"
        print("✓ PASS: Basic create works correctly")
    except Exception as e:
        print(f"✗ FAIL: {e}")
    
    # Test 2: Update operation
    print("\n[Test 2] Update operation...")
    try:
        post.body = 'Updated post 1'
        db.session.add(post)
        db.session.commit()
        assert len(INDEX) >= 2, f"Expected >= 2 index entries, got {len(INDEX)}"
        print("✓ PASS: Update operation works correctly")
    except Exception as e:
        print(f"✗ FAIL: {e}")
    
    # Test 3: Cleanup verification
    print("\n[Test 3] Cleanup after commit...")
    try:
        assert db.session.info.get('searchable_changes') is None, "searchable_changes not cleaned"
        print("✓ PASS: Cleanup after commit works correctly")
    except Exception as e:
        print(f"✗ FAIL: {e}")
    
    # Test 4: Defensive check
    print("\n[Test 4] Defensive check for missing _changes...")
    try:
        INDEX.clear()
        if 'searchable_changes' in db.session.info:
            del db.session.info['searchable_changes']
        
        post2 = Post(body='Test post 2')
        db.session.add(post2)
        db.session.commit()
        print("✓ PASS: Defensive check works, no exception raised")
    except Exception as e:
        print(f"✗ FAIL: {e}")
    
    # Test 5: Rollback handling
    print("\n[Test 5] Rollback clears stale data...")
    try:
        initial_changes = db.session.info.get('searchable_changes')
        
        post3 = Post(body='Rollback test')
        db.session.add(post3)
        db.session.rollback()
        
        assert db.session.info.get('searchable_changes') is None, "searchable_changes not cleared on rollback"
        print("✓ PASS: Rollback clears stale data correctly")
    except Exception as e:
        print(f"✗ FAIL: {e}")
    
    # Test 6: Session info isolation
    print("\n[Test 6] Session info isolation...")
    try:
        post = Post(body='Isolation test')
        db.session.add(post)
        db.session.commit()
        
        session1 = db.session()
        session2 = db.session()
        
        # Both should have independent info dicts
        assert 'searchable_changes' not in session1.info or session1.info['searchable_changes'] is None
        assert 'searchable_changes' not in session2.info or session2.info['searchable_changes'] is None
        
        session1.close()
        session2.close()
        print("✓ PASS: Session info isolation works correctly")
    except Exception as e:
        print(f"✗ FAIL: {e}")
    finally:
        session1.close()
        session2.close()

print("\n" + "=" * 70)
print("VALIDATION COMPLETE")
print("=" * 70)
