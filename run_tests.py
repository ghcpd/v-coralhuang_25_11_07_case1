import subprocess
import sys
import json

# Run the test
result = subprocess.run(
    [
        'C:/Bug_Bash/25_11_07/v-coralhuang_25_11_07_case1/.venv/Scripts/python.exe',
        '-m', 'pytest', 'test_concurrency.py', '-v', '--tb=short'
    ],
    cwd='c:\\Bug_Bash\\25_11_07\\v-coralhuang_25_11_07_case1',
    capture_output=True,
    text=True,
    timeout=60
)

with open('pytest_output.txt', 'w') as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\n\nReturn Code: {result.returncode}\n")

print("Results written to pytest_output.txt")
