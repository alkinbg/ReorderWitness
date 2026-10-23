"""Intentionally wrong: first-record-wins, though highest revision should win."""
import json
import sys

selected = {}
for line in sys.stdin:
    if not line.strip():
        continue
    record = json.loads(line)
    selected.setdefault(record["id"], record)
for key in sorted(selected):
    print(json.dumps(selected[key], sort_keys=True, ensure_ascii=False))
