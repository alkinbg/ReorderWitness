"""Intentionally wrong aggregation: groupby only merges adjacent equal keys."""

from __future__ import annotations

from itertools import groupby
import json
import sys


def main() -> None:
    rows = [json.loads(line) for line in sys.stdin if line.strip()]
    for customer, group in groupby(rows, key=lambda row: row["customer"]):
        print(json.dumps({
            "customer": customer,
            "total": sum(item["amount"] for item in group),
        }))


if __name__ == "__main__":
    main()
