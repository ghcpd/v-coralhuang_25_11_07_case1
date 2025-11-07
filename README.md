Project: flask_searchablemixin_buggy_version

Summary:
This small demo reproduces and fixes several concurrency and safety problems
in a SearchableMixin that integrates SQLAlchemy sessions with an external
search index. The original implementation attached mutable state to the
global `db.session`, did not clear residual state, and used instance-level
event wiring. These led to race conditions and lost index updates.

Fixes applied:
- Use `session.info` (per-session storage) instead of attaching `_changes` to
  the shared `db.session`.
- Add defensive checks for missing/malformed `searchable_changes`.
- Reinitialize per-transaction storage at `before_commit` to avoid residual
  state.
- Use SQLAlchemy `Session`-level event listeners via `event.listens_for`.
- Use a threading lock to make index updates atomic in this demo.
- Extended tests to cover concurrent commits, malformed session state, and
  confirming residual state is cleared.

How to run tests (Windows PowerShell):

1. Create a virtualenv and activate it
   python -m venv .venv; .\.venv\Scripts\Activate.ps1

2. Install requirements
   pip install -r requirements.txt

3. Run tests
   pytest -q

Or use the provided `run_test.sh` which wraps these steps and writes
`raw_results.json` and `output.json`.
