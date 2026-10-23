# ReorderWitness (research prototype)

**Find a short, reproducible input-order bug in a JSONL batch processor.**

This is an independent Python experiment, not a published PyPI release.
It does not depend on PHP, Symfony, databases, hosted services, or third-party runtime libraries.

## The problem

Some batch operations should be invariant to input order. Consider a deduplicator
that should select the highest version of each `id`. If it instead selects the
**first** record seen, changing the incoming order changes business results.
Simple happy-path tests can miss this.

ReorderWitness launches a **local program** that reads JSON Lines from stdin and
writes JSON Lines to stdout. It repeats the exact input to check for observed
nondeterminism; then tries a bounded series of reorderings, compares the output
**multiset** (not output line order), reduces a failing input by chunk removal,
and confirms the witness by rerunning each order twice. It saves both inputs,
both outputs and a machine-readable explanation.

It **does not prove** order independence in general. The input records and the
invariance assumption are supplied by the caller.

## Quick start (Python 3.11+)

From the repository root:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
reorderwitness --input examples/records.jsonl --output-dir /tmp/reorderwitness-broken -- python examples/processor_broken.py
# exit code 1: output difference found, evidence files written
reorderwitness --input examples/records.jsonl -- python examples/processor_correct.py
# exit code 0: no difference observed in bounded trials
```


### Independent example: graph connectivity

A connected-component finder must produce the same partition for any ordering
of an undirected graph's edges. The deliberately broken example performs just
one pass of label propagation, so two connected edges in a different order can
create different groups. The correct reference uses union-find.

```bash
reorderwitness --input examples/graph-components/edges.jsonl \
  --output-dir /tmp/reorderwitness-graph-broken -- \
  python examples/graph-components/processor_broken.py
# exit 1: order-dependent partition, reduced to 2 connected edges

reorderwitness --input examples/graph-components/edges.jsonl \
  -- python examples/graph-components/processor_correct.py
# exit 0: no difference observed in tested permutations (NOT proof)
```

These two examples use unrelated algorithms: revision selection and graph
connectivity. Both are intentionally synthetic; neither is evidence of market
adoption or comprehensive correctness.

On Windows, use an unused path under your temp directory instead of `/tmp`.
For direct execution without installation: `PYTHONPATH=src python -m reorderwitness ...`.

### CLI contract

- Input is UTF-8 JSON Lines containing **objects**, one per line.
- The target command is provided **after `--`**; it receives input on stdin.
- The target must return UTF-8 JSON objects, one per stdout line, exit code zero.
- Output order and JSON object key order are ignored; **duplicate row counts are preserved**.
- The target should be deterministic, isolated, read-only, and quick to run.
- A bug is when the same *multiset of input records*, in a different order, yields a different output multiset.

Exit codes: `0` = no difference observed (not a proof); `1` = confirmed difference;
`2` = inconclusive or usage/runtime error.

Options: `--trials`, `--seed`, `--timeout`, `--max-executions`,
`--max-records`, `--max-input-bytes`, `--max-output-bytes`,
`--max-total-seconds`, and `--output-dir`. Evidence is written only for a confirmed
mismatch and is never allowed to silently overwrite an existing directory.

## Safety and correctness limits

- **Never run against production, untrusted code, or an effectful job.** The command runs many
  times in the caller's environment. It is NOT sandboxed and receives normal
  permissions and environment variables. Run any questionable executable inside
  a separately configured, disposable, network-isolated container.
- The CLI limits JSONL input file size to 2 MiB (1000 records) by default;
  stdout is captured up to 2 MiB and stderr up to 64 KiB per execution.
  Exceeding these limits returns `INCONCLUSIVE` (exit `2`). These sizes can
  be changed; they are not a memory limit on the target process itself.
- Per-execution wall time defaults to 10 seconds, with a 120-second overall
  audit budget and at most 200 launched commands. The tool attempts to kill
  the target's process group on POSIX on timeouts and overflows; on Windows
  only the immediate child is terminated. Detached descendants may survive.
- A failure to execute, invalid JSON, timeout or inconsistent repeated output
  is reported as **inconclusive**, not a confirmed order bug.
- A fixed seed makes the tool's permutation search reproducible, not the target's
  own randomness, clocks, network or external state.
- Shrinking uses chunk deletion and finite trials. It is NOT guaranteed to find
  a globally minimal counterexample; it only preserves a witness when possible.
- Equality uses canonical JSON with duplicate counts; `1` and `1.0` remain
  distinct, and comparison ignores output row order, not nested array order.
- The command has no access to a claimed semantics of the target: legitimate
  order-sensitive operations will be flagged if the caller incorrectly asserts
  invariance.

## Project stage

Research spike suitable for an **experimental** public GitHub repository.
A second independent graph-connectivity scenario has been validated.
The GitHub name search has no exact matches, but PyPI name availability
remains unverified and must not be assumed. Subprocess output and wall time
are now bounded, but this is **not** CPU/memory isolation or a sandbox.
The GitHub Actions matrix includes Python 3.11, 3.12, and 3.13; successful
CI runs are still required before claiming compatibility with all three.
This project has not been published to PyPI. MIT license included.
