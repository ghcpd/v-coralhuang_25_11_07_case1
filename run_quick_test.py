#!/usr/bin/env python3
"""Quick test runner to capture output"""

import subprocess
import sys
import json
from pathlib import Path

def run_tests():
    """Run pytest and capture results"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_concurrency.py", "-v", "--tb=line", "-x"],
        capture_output=True,
        text=True
    )
    
    print("=" * 70)
    print("TEST EXECUTION OUTPUT")
    print("=" * 70)
    print(result.stdout)
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    print("\n" + "=" * 70)
    print(f"Return Code: {result.returncode}")
    print("=" * 70)
    
    return result

if __name__ == "__main__":
    run_tests()
