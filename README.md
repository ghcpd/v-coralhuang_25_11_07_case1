# flask_searchablemixin_buggy_version - Fixed

This project demonstrates fixes to a buggy SearchableMixin that mishandled session state and concurrent commits.

Issues fixed:
- Defensive checks for session search_changes
- Use of `session.info` to avoid per-process shared state
- Clear search_changes after commits or rollbacks
- Session-level event binding via `event.listens_for(Session, ...)`
- Atomic index updates via threading.Lock

How to run tests:
- On Linux/macOS: `bash run_test.sh`
- Or create a venv, install `requirements.txt` and run `pytest -q`
