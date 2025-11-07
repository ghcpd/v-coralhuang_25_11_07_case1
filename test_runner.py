import time
import json
import traceback
import importlib
from models import db, INDEX, init_db, engine, Base


def run_tests():
    init_db('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    results = []
    summary = {'passed': 0, 'failed': 0, 'errors': 0}

    tests = importlib.import_module('test_concurrency')
    # Collect callables starting with test_
    test_funcs = [(name, getattr(tests, name)) for name in dir(tests) if name.startswith('test_')]

    for name, func in test_funcs:
        INDEX.clear()
        start = time.time()
        ok = True
        err = None
        try:
            # Provide a transactional scoped session similar to pytest fixture
            connection = engine.connect()
            transaction = connection.begin()
            options = dict(bind=connection, binds={})
            sess = db.session.registry()
            db.session = sess

            try:
                func()
            finally:
                # Rollback changes and cleanup
                try:
                    transaction.rollback()
                except Exception:
                    pass
                try:
                    connection.close()
                except Exception:
                    pass
                try:
                    sess.remove()
                except Exception:
                    pass
        except AssertionError as e:
            ok = False
            err = {'type': 'assertion', 'message': str(e), 'traceback': traceback.format_exc()}
        except Exception as e:
            ok = False
            err = {'type': 'error', 'message': str(e), 'traceback': traceback.format_exc()}
        duration = time.time() - start
        results.append({'name': name, 'passed': ok, 'error': err, 'duration': duration})
        if ok:
            summary['passed'] += 1
        else:
            summary['failed'] += 1

    raw = {'tests': results, 'summary': summary}
    with open('raw_results.json', 'w') as f:
        json.dump(raw, f, indent=2)

    # Build audit report
    report = {
        'detected_issues': [
            'session._changes attached to global session',
            'no defensive checks for _changes',
            'no clearing of _changes after transactions',
            'no atomicity for index updates',
            'Session events not bound at Session class level',
            'tests did not cover rollback and malformed _changes'
        ],
        'modifications': [
            'Use session.info per-class keys for changes',
            'Defensive checks for change data structure',
            'Clear changes after commit/rollback',
            'Use threading.Lock for atomic index updates',
            'Bind event handlers to sqlalchemy.orm.Session'
        ],
        'test_results': raw
    }
    with open('output.json', 'w') as f:
        json.dump(report, f, indent=2)

    return raw, report


if __name__ == '__main__':
    raw, report = run_tests()
    print('Tests run:', raw['summary'])
