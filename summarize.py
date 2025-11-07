import json
r = json.load(open('raw_results.json'))
summary = {
    'total': r['summary']['total'],
    'passed': r['summary'].get('passed', 0),
    'failed': r['summary'].get('failed', 0),
    'skipped': r['summary'].get('skipped', 0),
    'duration': r.get('duration')
}

report = {
    'detected_issues': [
        'after_commit did not check for existence or type of session._changes',
        '_changes was not cleared between transactions, leaving residual data',
        '_changes attached to global db.session causing cross-thread pollution',
        'Index updates lacked atomicity leading to lost updates',
        'Event listeners bound to a specific session instance instead of Session class',
    ],
    'root_causes': [
        'Shared mutable state stored on the global session instance instead of per-session storage',
        'Lack of defensive checks and cleanup for transaction-bound state',
        'No locking around the mock index leading to race conditions',
        'Event binding to the wrong object led to inconsistent listener registration across sessions'
    ],
    'code_modifications': [
        'Migrate per-transaction changes from session._changes to session.info["searchable_changes"]',
        'Defensive checks for dict type and safe access in after_commit',
        'Always clear search changes in finally block after after_commit',
        'Register event listeners using sqlalchemy.event.listen(Session, ...)',
        'Add a threading.Lock-wrapped add_to_index to ensure atomic index updates',
        'Update tests to use app fixture, push app context in threads, and cover rollback, leftover, and concurrency cases'
    ],
    'pytest_summary': summary,
    'raw_report': r
}
open('output.json', 'w').write(json.dumps(report, indent=2))
print('Wrote output.json')
