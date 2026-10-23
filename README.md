# ReorderWitness

[![Tests](https://github.com/alkinbg/ReorderWitness/actions/workflows/tests.yml/badge.svg)](https://github.com/alkinbg/ReorderWitness/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Find input-order-dependent bugs in JSONL processors and save a small reproducer.**

If a batch operation *should* produce the same result for the same records in any order, ReorderWitness tests that assumption by launching your command with different record orders. When it finds a consistent difference, it attempts to reduce the input and writes the evidence to disk.

It is a **Python CLI research prototype**, not a library published on PyPI. You do not need to write a custom property-based test to try it against a compatible stdin/stdout program.

## A two-record example

Imagine a deduplicator that must select the record with the highest `version` for each `id`:

```jsonl
{"id":"alfa","version":1,"value":"old"}
{"id":"alfa","version":2,"value":"new"}
```

The deliberately broken example keeps the *first* record it sees. Reversing the input changes which value wins.

From a checkout of this repository (Python 3.11+):

```bash
python -m pip install -e .
reorderwitness --input examples/two-records.jsonl --output-dir evidence -- python examples/processor_broken.py
```

Example result:

```text
DIFFERENCE: 2 records reduced to 2; 7 executions
Evidence: evidence
```

The command returns exit code **1** when it confirms a difference. It saves `original-order.jsonl`, `reordered-input.jsonl`, both corresponding outputs, and `report.json` under the new `evidence/` directory. Execution counts depend on the search and may vary.

Try the correct implementation:

```bash
reorderwitness --input examples/two-records.jsonl -- python examples/processor_correct.py
```

This example exits **0** when no difference is observed in the attempted permutations. Exit 0 is **not proof** of order independence.

## Another independent example: graph connectivity

A connected-components calculator should return the same partition regardless of the order of an undirected graph's edges. The included broken one-pass algorithm violates that rule; ReorderWitness can reduce the counterexample to two connected edges.

```bash
reorderwitness --input examples/graph-components/edges.jsonl \
  --output-dir graph-evidence -- \
  python examples/graph-components/processor_broken.py
```

For the witness and expected results, see [the graph example](docs/graph-witness.md). These are synthetic demonstrations, not independent production integrations.

## A Python standard-library trap: `itertools.groupby`

Python's `itertools.groupby` groups **consecutive** matching keys; it is not an
order-independent SQL-style aggregation. The included synthetic example misuses
`groupby` on unsorted records and produces separate totals for the same customer.
ReorderWitness detects the inconsistency and preserves a three-record witness.

```bash
reorderwitness --input examples/groupby/records.jsonl \
  --output-dir groupby-evidence -- \
  python examples/groupby/processor_broken.py
```

For a correct comparison using `defaultdict`, see [the documented
example](docs/groupby-example.md), including the expected outputs and limitations.

## How it works

1. Run the same input twice to check for obvious nondeterminism.
2. Try a bounded number of permutations of the *same multiset* of input records.
3. Compare output as a multiset of JSON objects, not raw text; output row order and object key order do not matter, but duplicate counts do.
4. When a difference appears, remove chunks of records while attempting to preserve it.
5. Re-run both orders to confirm the witness, then write the inputs, outputs, and structured diff.

The reduction is **not guaranteed globally minimal**. The target's order-independence requirement comes from **you**: the tool cannot determine whether different output is actually a bug in your application.

## Input, output and exit codes

- **Input:** UTF-8 JSON Lines with one JSON **object** per nonblank line.
- **Target:** an executable command after `--`; it receives the JSONL input on stdin and must write JSON objects as JSONL on stdout with exit code 0.
- **Comparison:** output is compared as a multiset. Nested array ordering remains significant; `1` and `1.0` remain distinct.
- **Exit 0:** no difference observed within the configured search, **not a proof**.
- **Exit 1:** consistent order-dependent output observed.
- **Exit 2:** inconclusive, invalid input, resource budget exceeded, or CLI usage problem.
- **Report:** generated only for a confirmed difference. Existing output directories are **not overwritten**.

Run `reorderwitness --help` for available options: `--trials`, `--seed`, `--timeout`, `--max-executions`, `--max-records`, `--max-input-bytes`, `--max-output-bytes` and `--max-total-seconds`.

## Safety: read this before running against your program

**ReorderWitness is not a sandbox.** It runs the supplied command repeatedly with the caller's permissions, files, network access and environment variables. Only test **trusted, deterministic, isolated, side-effect-free** commands on disposable or synthetic input. Do not target production jobs, databases, payments, email senders, or arbitrary downloaded programs.

Default limits are 1,000 input records / 2 MiB of input, 2 MiB of captured stdout, 64 KiB of stderr, 10 seconds per invocation, 120 seconds overall and 200 executions. These are **tool-side budgets**, not CPU or RAM limits on the target. On POSIX the tool attempts to terminate the launched process group after an overrun; Windows cleanup only terminates the immediate process. Descendants that detach can survive.

Fixed seeds reproduce permutation selection, **not** external randomness or mutable state in the target. Invalid JSON, timeouts, overflows and unstable output return *inconclusive*, rather than falsely claiming a confirmed order bug.

Evidence files contain actual input and output records. Avoid secrets or personal data and do not upload sensitive evidence to public issues.

## Development

Supported interpreter range: Python **3.11+**. GitHub Actions currently tests **3.11, 3.12 and 3.13 on Ubuntu**; other environments, including Windows, have not been verified to the same extent. No third-party **runtime** dependencies are required.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributions, [SECURITY.md](SECURITY.md) for private vulnerability reports, [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for conduct, and [ACCESSIBILITY.md](ACCESSIBILITY.md) for CLI accessibility notes.

## Project status

**Experimental 0.1.0 source version.** This is a small, narrowly scoped black-box metamorphic test tool, not a replacement for [Hypothesis](https://hypothesis.readthedocs.io/) or other established test frameworks. All three demonstrated scenarios are synthetic. There is **no published PyPI package or official GitHub Release** yet.

The [research notes](docs/decision.bg.md) explain the initial scope and trade-offs. Contributions and independent use cases are welcome, but compatibility and performance guarantees beyond the documented tests are not claimed.

Released under the [MIT License](LICENSE).
