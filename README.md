# SearchableMixin Concurrency Fixes

This project demonstrates a fixed implementation of a SQLAlchemy/Flask SearchableMixin with enhanced safety and concurrency behavior.

## Summary of defects fixed
- Defensive checks for `session.info['search_changes']` to avoid AttributeError/TypeError
- `search_changes` is reinitialized at the start of each transaction to prevent stale data
- Use `session.info` for session-scoped state instead of mutating a global `db.session` object
- Atomic index updates using a `threading.Lock` to avoid race conditions during concurrent commits
- Event registration changed to `event.listens_for(Session, ...)` to ensure consistent behavior across sessions

## Files
- `models.py` — corrected `SearchableMixin` and session-level event bindings
- `test_concurrency.py` — expanded test suite to cover concurrency, rollback, and leftover states
- `requirements.txt` — dependencies for offline testing
- `run_test.sh` — convenience script to create venv, install deps, run tests, and write reports
- `output.json` — generated after running tests

## Reproducing locally
1. Run the test runner (POSIX, or run corresponding commands on Windows PowerShell):
   bash run_test.sh

2. On Windows PowerShell, use:
   python -m venv .venv; .\.venv\Scripts\Activate; pip install -r requirements.txt; pytest -q --json-report --json-report-file=raw_results.json

3. Inspect `raw_results.json` for detailed results and `output.json` for a summary.

## Notes
- The tests use a local SQLite database file `test_db.sqlite` and are simplified for reliability. The index is a mock list guarded by a lock to approximate atomic writes to an external index service.
- The event registration uses SQLAlchemy's Session-level events and uses `session.info` for thread/session isolation.
