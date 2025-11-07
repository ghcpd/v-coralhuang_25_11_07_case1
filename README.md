# Flask SearchableMixin — Reliability Fix

This project contains a corrected `SearchableMixin` implementation addressing concurrency, session-safety, and event binding issues.

Fixes applied:
- Use `session.info` for per-session storage instead of attaching attributes to `db.session`.
- Defensive checks for malformed or missing change data.
- Reinitialize and clear per-transaction change buffers.
- Bind event handlers to `sqlalchemy.orm.Session` using `event.listens_for`.
- Use a thread lock (`INDEX_LOCK`) to make index updates atomic and preserve ordering.
- Added tests for concurrent commits, missing/leftover changes, rollbacks, and session isolation.

How to run:

On Windows PowerShell, run:

```
./run_test.sh
```

This will create a virtual environment, install dependencies, run pytest, and produce `raw_results.json` and `output.json`.
