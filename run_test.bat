@echo off
REM Complete reproducible test environment setup and execution script (Windows)
REM This script creates venv, installs dependencies, runs tests, and generates reports

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ==== Flask SearchableMixin Bug Audit Test Suite ====
echo Working directory: %cd%
echo.

REM Step 1: Create virtual environment
echo [1/5] Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

REM Step 2: Activate virtual environment and install dependencies
echo [2/5] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

REM Step 3: Run tests with output
echo [3/5] Running test suite...
pytest test_concurrency.py -v --tb=short > test_output.log 2>&1
set TEST_EXIT_CODE=!ERRORLEVEL!

REM Display test output
type test_output.log

REM Step 4: Generate summary report
echo [4/5] Generating audit report...
python generate_report.py !TEST_EXIT_CODE!

echo [5/5] Test execution complete!
echo.
echo Reports generated:
if exist output.json (
    echo output.json - Found
) else (
    echo output.json - Not found
)
if exist test_output.log (
    echo test_output.log - Found
) else (
    echo test_output.log - Not found
)
echo.
echo To review full results: type output.json
echo To see test output: type test_output.log
