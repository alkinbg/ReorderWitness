# An order-dependence trap with Python's itertools.groupby

Python's [`itertools.groupby`](https://docs.python.org/3/library/itertools.html#itertools.groupby)
groups **consecutive** items with equal keys. It does not automatically aggregate
all records with the same key, as SQL `GROUP BY` typically does.

This is correct documented Python behavior. The example demonstrates a **misuse**
in an application that incorrectly assumes each customer receives one total,
regardless of input order.

## The same three input records

```jsonl
{"customer":"A","amount":10}
{"customer":"B","amount":5}
{"customer":"A","amount":8}
```

For input order **A, B, A**, the broken implementation emits:

```jsonl
{"customer": "A", "total": 10}
{"customer": "B", "total": 5}
{"customer": "A", "total": 8}
```

For order **A, A, B**, it emits:

```jsonl
{"customer": "A", "total": 18}
{"customer": "B", "total": 5}
```

The expected aggregation is one row per customer: **A=18, B=5**. ReorderWitness
detects the different output **multisets**. In a local Python 3.12 experiment,
it reported `DIFFERENCE: 3 records reduced to 3; 16 executions`.
Execution counts are not a stable API guarantee.

## Reproduce

From the project root, after `python -m pip install -e .`:

```bash
reorderwitness --input examples/groupby/records.jsonl \
  --output-dir groupby-evidence -- \
  python examples/groupby/processor_broken.py
# expected exit code 1: confirmed different outputs
```

```bash
reorderwitness --input examples/groupby/records.jsonl \
  -- python examples/groupby/processor_correct.py
# expected exit code 0: no difference observed in the sampled permutations
```

The correct version accumulates by key with `collections.defaultdict(int)`.
Sorting by key before calling `itertools.groupby` would also work for a finite
input, at the cost of sorting. `defaultdict` can aggregate a stream without
sorting, but its memory use still depends on the number of distinct keys.

## What this example establishes

- It reproduces an **order-dependent application mistake**, not a bug in CPython.
- `groupby` was designed to group *runs* of keys and is useful when that is
  exactly the desired behavior.
- A finite permutation search cannot prove general correctness: exit code 0
  means **no difference observed** in the tested cases.
- The example is synthetic, deterministic, and safe to execute locally. It is
  not evidence that ReorderWitness found a production vulnerability or bug.

Do not use this CLI to run untrusted or side-effecting production commands:
ReorderWitness is not a sandbox.
