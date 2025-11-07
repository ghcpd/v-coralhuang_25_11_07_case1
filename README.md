# Flask SearchableMixin Reliability Fixes

This project demonstrates fixes to a buggy `SearchableMixin` and provides tests showing the concurrency and state-isolation issues.

## Issues Fixed

- Defensive checks for missing or malformed per-session change storage
- Use `session.info` for session-local storage instead of attaching attributes directly to `db.session`
- Clear `searchable_changes` after commit and after rollback to avoid stale residual state
- Use SQLAlchemy `event.listens_for(Session, ...)` event bindings instead of binding to a global `db.session`
- Add atomic index updates using a threading lock to avoid race conditions when appending to the mock index
- Add tests covering concurrent commits, missing/leftover changes, rollback cleanup, and ordering

## How to run

- Use PowerShell: `.









- Production code should replace `add_to_index` with actual search index logic and handle failures/retries accordingly.- `INDEX` is a very small mock in-memory list intended to emulate external index updates.- Tests use a file-backed SQLite database (`test.db`) and configure `check_same_thread=False` so multiple threads can access the same DB.## Notes & DesignThis will install dependencies in `.venv`, run tests and output both `raw_results.json` and a `output.json` summary.- Or use Bash: `./run_test.sh`un_test.ps1` (recommended for Windows)