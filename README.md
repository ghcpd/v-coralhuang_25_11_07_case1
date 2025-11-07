# flask_searchablemixin_buggy_version - Reliability Fixes and Tests

## Summary
This repository demonstrates a corrected implementation of a SearchableMixin
that integrates SQLAlchemy ORM models with a mock search index. The original
implementation suffered from multiple concurrency and event binding issues;
this project provides fixes, tests, and scripts to verify behavior.

## Problems in original implementation
- after_commit did not check for existence or type of `session._changes`.
- `_changes` was not cleared between transactions, leaving residual data.
- `_changes` was attached directly to the global `db.session`, which is not
  session-safe and caused data leakage across threads.
- Index updates were not atomic, leading to lost or out-of-order updates.
- Event listeners were bound to a specific `db.session` instance instead of
  the SQLAlchemy `Session` class.
- Tests did not cover rollback scenarios, leftover state, or multi-threaded
  creation/updates.

## Technical Fixes
- Use `session.info['searchable_changes']` (per-session dict) for storing
  transaction-local change lists.
- Defensively validate `searchable_changes` and clear it in `after_commit`.
- Register listeners on `sqlalchemy.orm.Session` via `event.listen`.
- Make index updates atomic by protecting the in-memory index with a `threading.Lock`.
- Expand tests to cover concurrent updates, rollback scenarios, leftover/malformed state, and concurrent creation.

## Files
- `models.py`: Implemented fixes described above.
- `test_concurrency.py`: Test suite covering multiple edge cases.
- `requirements.txt`: All packages needed to run tests.
- `run_test.sh`, `run_test.ps1`: Scripts to create a venv, install deps, and run tests.
- `README.md`: This file.

## Running tests
On Linux/macOS with Bash:

    ./run_test.sh

On Windows PowerShell:

    .\run_test.ps1

This will create a Python virtual environment, install dependencies, run pytest
and write raw results to `raw_results.json` and a summary to `output.json`.

## Notes
- Tests use a file-based SQLite DB to allow threads to share the same database.
- The mock index is an in-memory list guarded by a lock to simulate atomic
  updates to an external search index (like Elasticsearch).

