# SearchableMixin Concurrency Fixes

This project demonstrates fixes to a buggy `SearchableMixin` that integrated SQLAlchemy ORM events with a search index in an unsafe way.

## Original Defects
- `after_commit` assumed `session._changes` existed and was a dict, causing AttributeError/TypeError.
- `_changes` was left on the global session across transactions, producing stale data.
- Shared mutable state was attached directly to `db.session`, not session-scoped or thread-safe.
- Index updates were non-atomic and could be lost in concurrent commits.
- Event registration used `db.event.listen(db.session, ...)` which binds to a single session instance.

## Fixes Implemented
- Use `session.info` (a per-session dict) to store transactional changes safely.
- Defensively check types and existence before accessing `searchable_changes`.
- Reinitialize/clear per-transaction changes at `before_commit`.
- Use a thread-safe `MockIndex` with a lock to simulate atomic index writes.
- Register listeners at the SQLAlchemy `Session` level using `event.listens_for(Session, ...)`.

## Files
- `models.py`: corrected `SearchableMixin`, `Post` model, `MockIndex` implementation, and Session-level event listeners.
- `test_concurrency.py`: expanded tests covering concurrent commits, malformed/leftover `searchable_changes`, and rollback scenarios.
- `requirements.txt`: dependencies for reproduction.
- `run_test.sh`: script to create venv, install deps, run tests, and produce `raw_results.json` and `output.json`.

## How to run
On Unix-like systems:

```bash
./run_test.sh
```

On Windows (PowerShell):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest -q --tb=short --json-report --json-report-file=raw_results.json; python -c "import json; r=json.load(open('raw_results.json')); summary={'total':r.get('summary',{}).get('total',0),'passed':r.get('summary',{}).get('passed',0),'failed':r.get('summary',{}).get('failed',0)}; json.dump({'summary':summary,'raw':r}, open('output.json','w'), indent=2); print('Wrote output.json')"
```

Note: This environment uses SQLite in-memory DB for tests and a mock index; no external services required.
