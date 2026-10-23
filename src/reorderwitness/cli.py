"""CLI for testing order sensitivity of JSON Lines transformations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .core import OrderAuditor, parse_jsonl, serialize_records


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reorderwitness",
        description="Find record-order-dependent output from a deterministic JSONL stdin/stdout command.",
        epilog="Example: reorderwitness --input records.jsonl --output-dir evidence -- python worker.py",
    )
    parser.add_argument("--input", type=Path, required=True, help="Input JSONL (one JSON object per line)")
    parser.add_argument("--output-dir", type=Path, default=Path("reorderwitness-evidence"), help="New directory for witness files")
    parser.add_argument("--trials", type=int, default=30, help="Maximum distinct permutations to try per subset")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (also influences shrinking)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Seconds allowed per target execution")
    parser.add_argument("--max-executions", type=int, default=200, help="Maximum total subprocess executions")
    parser.add_argument("--max-records", type=int, default=1000, help="Maximum input records to load")
    parser.add_argument("--max-input-bytes", type=int, default=2 * 1024 * 1024, help="Maximum size of input JSONL file (default 2 MiB)")
    parser.add_argument("--max-output-bytes", type=int, default=2 * 1024 * 1024, help="Maximum captured stdout bytes per execution (default 2 MiB)")
    parser.add_argument("--max-total-seconds", type=float, default=120, help="Wall-clock budget for whole audit (default 120 seconds)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Target command after --")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if (args.trials < 1 or args.timeout <= 0 or args.max_executions < 7 or args.max_records < 2
            or args.max_input_bytes < 1 or args.max_output_bytes < 1 or args.max_total_seconds <= 0):
        parser.error("limits must be positive, max-executions >= 7 and max-records >= 2")
    command = list(args.command)
    if not command or command[0] != "--" or len(command) < 2:
        parser.error("provide a target command after --, e.g. -- python processor.py")
    command = command[1:]
    try:
        if args.input.stat().st_size > args.max_input_bytes:
            raise ValueError(f"input file exceeds {args.max_input_bytes} bytes")
        records = parse_jsonl(args.input.read_text(encoding="utf-8"), label=str(args.input))
        if not 2 <= len(records) <= args.max_records:
            raise ValueError(f"expected 2..{args.max_records} records, received {len(records)}")
        outcome = OrderAuditor(
            command, timeout=args.timeout, max_executions=args.max_executions,
            max_output_bytes=args.max_output_bytes, max_total_seconds=args.max_total_seconds,
        ).audit(
            records, trials=args.trials, seed=args.seed
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if outcome.status == "inconclusive":
        print(f"INCONCLUSIVE: {outcome.reason} (executions={outcome.executions})", file=sys.stderr)
        return 2
    if outcome.status == "no_difference_observed":
        print(f"NO DIFFERENCE OBSERVED: {outcome.reason} (executions={outcome.executions})")
        return 0

    assert outcome.witness is not None
    witness = outcome.witness
    # Refuse overwrite. Writing a witness may expose sensitive user-supplied records.
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / "original-order.jsonl").write_text(serialize_records(witness.baseline_input), encoding="utf-8")
        (args.output_dir / "reordered-input.jsonl").write_text(serialize_records(witness.reordered_input), encoding="utf-8")
        (args.output_dir / "original-output.jsonl").write_text(witness.baseline.raw, encoding="utf-8")
        (args.output_dir / "reordered-output.jsonl").write_text(witness.reordered.raw, encoding="utf-8")
        report = {
            "status": outcome.status,
            "reason": outcome.reason,
            "input_record_count": outcome.original_count,
            "witness_record_count": len(witness.baseline_input),
            "minimization_complete": outcome.minimization_complete,
            "executions": outcome.executions,
            "seed": args.seed,
            "trials": args.trials,
            "target_command": command,
            "difference": witness.diff(),
            "limitation": "A sampled, repeated witness; no proof of correctness for all inputs or all orders.",
        }
        (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write evidence: {exc}", file=sys.stderr)
        return 2
    print(f"DIFFERENCE: {outcome.original_count} records reduced to {len(witness.baseline_input)}; {outcome.executions} executions")
    print(f"Evidence: {args.output_dir}")
    if not outcome.minimization_complete:
        print("Note: minimization stopped at execution limit; witness is still confirmed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
