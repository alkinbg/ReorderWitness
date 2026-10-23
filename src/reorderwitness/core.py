"""Find witnessed sensitivity to input record ordering in isolated CLI processors."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import math
import os
import random
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any, Iterator, Literal, Sequence

JsonRecord = dict[str, Any]


def serialize_records(records: Sequence[JsonRecord]) -> str:
    """Encode JSON objects as one line per record, including a final newline."""
    return "".join(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n" for value in records)


def parse_jsonl(text: str, *, label: str) -> list[JsonRecord]:
    """Parse strictly JSON object lines. Ignore empty lines."""
    def reject_non_finite(value: str) -> None:
        raise ValueError(f"non-standard JSON numeric constant: {value}")

    result: list[JsonRecord] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw, parse_constant=reject_non_finite)
        except ValueError as exc:
            raise ValueError(f"{label}: invalid JSON at line {line_number}: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"{label}: JSON value at line {line_number} must be an object")
        result.append(obj)
    return result


def canonical_bag(records: Sequence[JsonRecord]) -> Counter[str]:
    """Compare output as a MULTISET of objects, ignoring object-key and line order.

    Multiplicity is preserved: two identical rows are not the same as one row.
    Numeric JSON representation is preserved (e.g. 1 versus 1.0).
    """
    return Counter(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) for record in records)


@dataclass(frozen=True)
class Result:
    raw: str
    bag: Counter[str]


class TargetError(Exception):
    """The target command could not be reliably tested."""


class BudgetExceeded(Exception):
    """The configured maximum number of command executions was reached."""


def _kill_target(process: subprocess.Popen[bytes]) -> None:
    """Kill the launched process group on POSIX; the direct child on Windows.

    This is a cleanup mechanism, NOT a sandbox or a guarantee that a target
    cannot spawn detached processes.
    """
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()


def _read_limited(stream: Any, *, limit: int, data: bytearray, overflow: threading.Event) -> None:
    """Drain a subprocess pipe without retaining an unbounded response."""
    try:
        while not overflow.is_set():
            chunk = stream.read(32768)
            if not chunk:
                return
            remaining = limit - len(data)
            if len(chunk) > remaining:
                data.extend(chunk[:remaining])
                overflow.set()
                return
            data.extend(chunk)
    except (OSError, ValueError):
        # A concurrent timeout/forced shutdown may close a pipe.
        return


def _run_limited_process(
    command: Sequence[str], input_data: bytes, *, timeout: float,
    max_output_bytes: int, max_stderr_bytes: int,
) -> tuple[int, str, str]:
    """Execute a target with bounded captured output and a wall-clock timeout.

    Uses a file-backed stdin to avoid a blocked stdin writer competing with the
    two output readers. No shell and no sandbox are involved.
    """
    with tempfile.TemporaryFile(mode="w+b") as source:
        source.write(input_data)
        source.seek(0)
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                command,
                stdin=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            raise TargetError(f"failed to execute target: {exc}") from exc

        assert process.stdout is not None and process.stderr is not None
        stdout = bytearray()
        stderr = bytearray()
        output_overflow = threading.Event()
        error_overflow = threading.Event()
        readers = [
            threading.Thread(target=_read_limited, args=(process.stdout,), kwargs={"limit": max_output_bytes, "data": stdout, "overflow": output_overflow}, daemon=True),
            threading.Thread(target=_read_limited, args=(process.stderr,), kwargs={"limit": max_stderr_bytes, "data": stderr, "overflow": error_overflow}, daemon=True),
        ]
        for reader in readers:
            reader.start()

        deadline = time.monotonic() + timeout
        failure: str | None = None
        try:
            while True:
                if output_overflow.is_set():
                    failure = f"target stdout exceeded {max_output_bytes} bytes"
                    break
                if error_overflow.is_set():
                    failure = f"target stderr exceeded {max_stderr_bytes} bytes"
                    break
                if process.poll() is not None and all(not reader.is_alive() for reader in readers):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    failure = f"target timed out after {timeout:g} seconds"
                    break
                time.sleep(min(0.01, remaining))
        finally:
            if failure is not None:
                _kill_target(process)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                _kill_target(process)
                process.wait(timeout=1)
            for reader, pipe in zip(readers, (process.stdout, process.stderr)):
                reader.join(timeout=1)
                # On Windows a descendant can retain an inherited pipe handle.
                # Closing a buffered pipe while another thread is blocked in
                # read() can itself hang: favor a daemon-thread leak over a
                # permanently wedged CLI in this already-inconclusive case.
                if not reader.is_alive():
                    pipe.close()

        if failure is not None:
            raise TargetError(failure)
        try:
            return process.returncode, stdout.decode("utf-8", errors="strict"), stderr.decode("utf-8", errors="replace")
        except UnicodeError as exc:
            raise TargetError(f"target stdout was not valid UTF-8: {exc}") from exc


@dataclass(frozen=True)
class Witness:
    baseline_input: tuple[JsonRecord, ...]
    reordered_input: tuple[JsonRecord, ...]
    baseline: Result
    reordered: Result

    def diff(self) -> dict[str, list[dict[str, Any]]]:
        missing = self.baseline.bag - self.reordered.bag
        extra = self.reordered.bag - self.baseline.bag
        return {
            "only_in_original_order": [
                {"record": json.loads(row), "count": count} for row, count in sorted(missing.items())
            ],
            "only_in_reordered_input": [
                {"record": json.loads(row), "count": count} for row, count in sorted(extra.items())
            ],
        }


@dataclass(frozen=True)
class Audit:
    status: Literal["difference", "no_difference_observed", "inconclusive"]
    reason: str
    executions: int
    original_count: int
    witness: Witness | None = None
    minimization_complete: bool = True


def _permutations(count: int, trials: int, seed: int) -> Iterator[tuple[int, ...]]:
    """Deterministic bounded search: reversal, adjacent swaps, seeded shuffles."""
    if count < 2:
        return
    original = tuple(range(count))
    seen: set[tuple[int, ...]] = {original}
    rng = random.Random(seed)
    candidates = [tuple(reversed(original))]
    for i in range(count - 1):
        indexes = list(original)
        indexes[i], indexes[i + 1] = indexes[i + 1], indexes[i]
        candidates.append(tuple(indexes))
    emitted = 0
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            yield candidate
            emitted += 1
            if emitted >= trials:
                return
    # Bound duplicate-draw attempts, even when n! < trials + 1.
    for _ in range(trials * 5):
        indexes = list(original)
        rng.shuffle(indexes)
        candidate = tuple(indexes)
        if candidate not in seen:
            seen.add(candidate)
            yield candidate
            emitted += 1
            if emitted >= trials:
                return


class OrderAuditor:
    """Run a local CLI transform many times; commands must be safe to repeat.

    No shell is invoked. Do NOT point this at stateful production workloads.
    """

    def __init__(
        self, command: Sequence[str], *, timeout: float = 10.0, max_executions: int = 200,
        max_output_bytes: int = 2 * 1024 * 1024, max_stderr_bytes: int = 64 * 1024,
        max_total_seconds: float = 120.0,
    ):
        if not command or not all(command):
            raise ValueError("command must contain at least one nonempty argument")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_executions < 7:
            raise ValueError("max_executions must be at least 7")
        if max_output_bytes < 1 or max_stderr_bytes < 1 or max_total_seconds <= 0:
            raise ValueError("output limits and total runtime must be positive")
        self.command = tuple(command)
        self.timeout = timeout
        self.max_executions = max_executions
        self.max_output_bytes = max_output_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self.max_total_seconds = max_total_seconds
        self.executions = 0
        self._started: float | None = None

    def _run(self, records: Sequence[JsonRecord], *, reserve: int = 4) -> Result:
        if self.executions >= self.max_executions - reserve:
            raise BudgetExceeded("execution budget exhausted")
        remaining = self.max_total_seconds - (time.monotonic() - (self._started or time.monotonic()))
        if remaining <= 0:
            raise BudgetExceeded("overall runtime budget exhausted")
        self.executions += 1
        code, out, err = _run_limited_process(
            self.command, serialize_records(records).encode("utf-8"),
            timeout=min(self.timeout, remaining), max_output_bytes=self.max_output_bytes,
            max_stderr_bytes=self.max_stderr_bytes,
        )
        if code != 0:
            raise TargetError(f"target exited with code {code}: {err.strip()[:300]}")
        try:
            records_out = parse_jsonl(out, label="target stdout")
        except ValueError as exc:
            raise TargetError(str(exc)) from exc
        return Result(raw=out, bag=canonical_bag(records_out))

    def _find(self, records: Sequence[JsonRecord], *, trials: int, seed: int, base: Result | None = None) -> Witness | None:
        original = tuple(records)
        baseline = base if base is not None else self._run(original)
        for permutation in _permutations(len(original), trials, seed):
            shuffled = tuple(original[i] for i in permutation)
            alternate = self._run(shuffled)
            if baseline.bag != alternate.bag:
                return Witness(original, shuffled, baseline, alternate)
        return None

    def _shrink(self, witness: Witness, *, trials: int, seed: int) -> tuple[Witness, bool]:
        """Delta-debug by removing contiguous chunks; not a global minimality proof."""
        best = witness
        items = list(witness.baseline_input)
        granularity = 2
        try:
            while len(items) > 2:
                chunk_size = math.ceil(len(items) / granularity)
                changed = False
                for start in range(0, len(items), chunk_size):
                    reduced = items[:start] + items[start + chunk_size :]
                    if len(reduced) < 2:
                        continue
                    candidate = self._find(reduced, trials=trials, seed=seed)
                    if candidate is not None:
                        best = candidate
                        items = reduced
                        granularity = max(2, granularity - 1)
                        changed = True
                        break
                if not changed:
                    if granularity >= len(items):
                        break
                    granularity = min(len(items), granularity * 2)
        except BudgetExceeded:
            return best, False
        return best, True

    def _confirm(self, witness: Witness) -> bool:
        """Repeat each EXACT order twice, detecting observed target instability."""
        a1 = self._run(witness.baseline_input, reserve=0)
        a2 = self._run(witness.baseline_input, reserve=0)
        b1 = self._run(witness.reordered_input, reserve=0)
        b2 = self._run(witness.reordered_input, reserve=0)
        return a1.bag == a2.bag and b1.bag == b2.bag and a1.bag != b1.bag and a1.bag == witness.baseline.bag and b1.bag == witness.reordered.bag

    def audit(self, rows: Sequence[JsonRecord], *, trials: int = 30, seed: int = 42) -> Audit:
        if self.executions:
            raise ValueError("create a new OrderAuditor for each audit")
        self._started = time.monotonic()
        if trials < 1:
            raise ValueError("trials must be positive")
        if len(rows) < 2:
            raise ValueError("at least two JSONL records are required")
        # Avoid infinite/NaN invalid in-process programmatic inputs.
        serialize_records(rows)
        try:
            base = self._run(rows)
            base_again = self._run(rows)
            if base.bag != base_again.bag:
                return Audit("inconclusive", "same input already produced different outputs", self.executions, len(rows))
            witness = self._find(rows, trials=trials, seed=seed, base=base)
        except (TargetError, BudgetExceeded) as exc:
            return Audit("inconclusive", str(exc), self.executions, len(rows))
        if witness is None:
            return Audit("no_difference_observed", f"no output difference observed within {trials} trial permutations", self.executions, len(rows))
        try:
            minimized, completed = self._shrink(witness, trials=trials, seed=seed)
            if not self._confirm(minimized):
                return Audit("inconclusive", "witness did not reproduce consistently on confirmation", self.executions, len(rows))
        except (TargetError, BudgetExceeded) as exc:
            return Audit("inconclusive", f"failed to confirm witness: {exc}", self.executions, len(rows))
        return Audit("difference", "input order changed the output multiset", self.executions, len(rows), minimized, completed)
