"""Correct for this example: maximum version, deterministic tie-breaker."""
import json
import sys

selected = {}
for line in sys.stdin:
    if not line.strip():
        continue
    record = json.loads(line)
    old = selected.get(record["id"])
    # Tie-break deterministically on normalized JSON, without input-order preference.
    def key(r):
        return (r["version"], json.dumps(r, sort_keys=True, ensure_ascii=False))
    if old is None or key(record) > key(old):
        selected[record["id"]] = record
for name in sorted(selected):
    print(json.dumps(selected[name], sort_keys=True, ensure_ascii=False))
