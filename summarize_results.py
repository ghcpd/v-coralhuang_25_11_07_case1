import json

try:
    with open('raw_results.json') as f:
        r = json.load(f)
except FileNotFoundError:
    print('raw_results.json not found')
    raise SystemExit(1)

summary = {'passed': 0, 'failed': 0, 'skipped': 0}
for test in r.get('tests', []):
    outcome = test.get('outcome')
    if outcome == 'passed':
        summary['passed'] += 1
    elif outcome == 'failed':
        summary['failed'] += 1
    elif outcome == 'skipped':
        summary['skipped'] += 1

summary['duration'] = r.get('duration')

print('Summary:', summary)
with open('output.json', 'w') as f:
    json.dump({'summary': summary, 'raw': r}, f, indent=2)
