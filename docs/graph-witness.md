# Graph connectivity — reproduced black-box counterexample

The command-line tool detected an input-order dependency in a deliberately
broken connected-component algorithm. The same 5 edges were supplied in
reordered sequences. The witness was shrunk to just **two connected edges**.

Run from the repository root after installing the wheel or editable package:

```bash
reorderwitness --input examples/graph-components/edges.jsonl \
  --output-dir graph-evidence --trials 8 -- \
  python examples/graph-components/processor_broken.py
```

Observed exit status: **1**. The evidence report recorded 15 child-process
executions, and `minimization_complete: true`.

## Witness inputs

Original ordering:

```jsonl
{"u":"C","v":"D"}
{"u":"B","v":"C"}
```

Reordered:

```jsonl
{"u":"B","v":"C"}
{"u":"C","v":"D"}
```

## Observed difference

- In the first order, the broken processor returned components `[B,C]` and `[D]`.
- In the second order, it returned component `[B,C,D]`.
- Both inputs represent the same undirected graph. The correct answer is `[B,C,D]`.

The separate reference implementation uses union-find. In the same bounded
experiment it reported `NO DIFFERENCE OBSERVED` (exit status 0), **not** a
mathematical proof of order independence for arbitrary inputs.

## Scope

This example was executed with Python 3.13 on 2026-10-23. The programs are
small synthetic test fixtures. ReorderWitness has not been validated against
an independent production dataset. `subprocess` is not sandboxed; do not run
this test harness against stateful production workloads.
