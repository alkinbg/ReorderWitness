"""Order-independent streaming aggregation with defaultdict."""

from __future__ import annotations

from collections import defaultdict
import json
import sys


def main() -> None:
    totals: defaultdict[str, int] = defaultdict(int)
    for line in sys.stdin:
        if line.strip():
            row = json.loads(line)
            totals[row["customer"]] += row["amount"]

    for customer, total in sorted(totals.items()):
        print(json.dumps({"customer": customer, "total": total}))


if __name__ == "__main__":
    main()
