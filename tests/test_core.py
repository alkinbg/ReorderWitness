from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from reorderwitness.core import BudgetExceeded, OrderAuditor, Result, canonical_bag, parse_jsonl

ROOT = Path(__file__).resolve().parents[1]
ROWS = parse_jsonl((ROOT / "examples" / "records.jsonl").read_text(encoding="utf-8"), label="example")


def first_wins(records):
    chosen = {}
    for record in records:
        chosen.setdefault(record["id"], record)
    return [chosen[key] for key in sorted(chosen)]


def highest_version(records):
    chosen = {}
    for record in records:
        previous = chosen.get(record["id"])
        key = lambda r: (r["version"], json.dumps(r, sort_keys=True))
        if previous is None or key(record) > key(previous):
            chosen[record["id"]] = record
    return [chosen[key] for key in sorted(chosen)]


class InProcessAuditor(OrderAuditor):
    """Unit-test algorithm without external interpreter startup overhead."""

    def __init__(self, processor, *, max_executions=200):
        super().__init__(["unit-test-process"], max_executions=max_executions)
        self.processor = processor

    def _run(self, records, *, reserve=4):
        if self.executions >= self.max_executions - reserve:
            raise BudgetExceeded("execution budget exhausted")
        self.executions += 1
        output = self.processor(records)
        return Result("".join(json.dumps(x) + "\n" for x in output), canonical_bag(output))


class TestParsing(unittest.TestCase):
    def test_blank_lines_ignored(self):
        self.assertEqual(parse_jsonl(' {"x": 1}\n\n{"x":2}\n', label="x"), [{"x": 1}, {"x": 2}])

    def test_invalid_json_rejected(self):
        with self.assertRaisesRegex(ValueError, "line 2"):
            parse_jsonl('{"x":1}\nBAD', label="input")

    def test_nonstandard_nan_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-standard JSON numeric constant"):
            parse_jsonl('{"x":NaN}', label="input")

    def test_non_object_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be an object"):
            parse_jsonl('[1,2]', label="x")

    def test_bag_ignores_record_order_and_object_key_order(self):
        self.assertEqual(canonical_bag([{"a": 1, "b": 2}, {"a": 2}]), canonical_bag([{"a": 2}, {"b": 2, "a": 1}]))

    def test_bag_preserves_duplicates(self):
        self.assertNotEqual(canonical_bag([{"a": 1}]), canonical_bag([{"a": 1}, {"a": 1}]))

    def test_distinguishes_numeric_representations(self):
        self.assertNotEqual(canonical_bag([{"a": 1}]), canonical_bag([{"a": 1.0}]))


class TestOrderAuditor(unittest.TestCase):
    def test_detects_and_reduces_bug_to_two_records(self):
        audit = InProcessAuditor(first_wins).audit(ROWS, trials=30, seed=42)
        self.assertEqual(audit.status, "difference", audit.reason)
        witness = audit.witness
        self.assertIsNotNone(witness)
        self.assertEqual(len(witness.baseline_input), 2)
        self.assertEqual(len(witness.reordered_input), 2)
        self.assertEqual(witness.baseline_input[0]["id"], witness.baseline_input[1]["id"])
        self.assertTrue(witness.diff()["only_in_original_order"])
        self.assertTrue(witness.diff()["only_in_reordered_input"])

    def test_seed_is_reproducible(self):
        a = InProcessAuditor(first_wins).audit(ROWS, trials=15, seed=91)
        b = InProcessAuditor(first_wins).audit(ROWS, trials=15, seed=91)
        self.assertEqual(a.status, b.status)
        self.assertEqual(a.witness.baseline_input, b.witness.baseline_input)
        self.assertEqual(a.witness.reordered_input, b.witness.reordered_input)

    def test_correct_processor_has_no_observed_difference(self):
        audit = InProcessAuditor(highest_version).audit(ROWS, trials=30)
        self.assertEqual(audit.status, "no_difference_observed", audit.reason)

    def test_empty_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            InProcessAuditor(highest_version).audit([])

    def test_one_trial_allowed(self):
        audit = InProcessAuditor(first_wins).audit(ROWS, trials=1)
        self.assertEqual(audit.status, "difference")

    def test_invalid_trial_count(self):
        with self.assertRaises(ValueError):
            InProcessAuditor(highest_version).audit(ROWS, trials=0)

    def test_invalid_timeout(self):
        with self.assertRaises(ValueError):
            OrderAuditor(["command"], timeout=0)

    def test_invalid_max_executions(self):
        with self.assertRaises(ValueError):
            InProcessAuditor(highest_version, max_executions=6)

    def test_short_execution_budget_is_inconclusive_for_no_mismatch(self):
        audit = InProcessAuditor(highest_version, max_executions=7).audit(ROWS, trials=30)
        self.assertEqual(audit.status, "inconclusive")
        self.assertIn("budget", audit.reason)

    def test_same_input_instability_is_inconclusive(self):
        counter = iter(range(10))
        def nondeterministic(_):
            return [{"serial": next(counter)}]
        audit = InProcessAuditor(nondeterministic).audit(ROWS)
        self.assertEqual(audit.status, "inconclusive")
        self.assertIn("same input", audit.reason)

    def test_single_item_will_not_lead_to_false_difference(self):
        audit = InProcessAuditor(first_wins).audit([{"id":"a","version":1},{"id":"b","version":2}])
        self.assertEqual(audit.status, "no_difference_observed")

    def test_budget_while_shrinking_retains_confirmed_difference(self):
        audit = InProcessAuditor(first_wins, max_executions=12).audit(ROWS, trials=30)
        self.assertEqual(audit.status, "difference", audit.reason)
        self.assertFalse(audit.minimization_complete)
        self.assertIsNotNone(audit.witness)

    def test_an_auditor_cannot_silently_reuse_exhausted_budgets(self):
        auditor = InProcessAuditor(highest_version)
        auditor.audit(ROWS, trials=1)
        with self.assertRaisesRegex(ValueError, "new OrderAuditor"):
            auditor.audit(ROWS, trials=1)

    def test_rejects_invalid_resource_limits(self):
        with self.assertRaisesRegex(ValueError, "output limits"):
            OrderAuditor([sys.executable], max_output_bytes=0)


class TestBoundedSubprocess(unittest.TestCase):
    def test_stdout_overflow_is_inconclusive_not_a_difference(self):
        target = [sys.executable, "-c", "import os; os.write(1, b'x' * 16384)"]
        audit = OrderAuditor(target, max_output_bytes=512, timeout=2).audit([{"a": 1}, {"a": 2}])
        self.assertEqual(audit.status, "inconclusive")
        self.assertIn("stdout exceeded 512 bytes", audit.reason)

    def test_stderr_overflow_is_inconclusive(self):
        target = [sys.executable, "-c", "import os; os.write(2, b'x' * 16384)"]
        audit = OrderAuditor(target, max_stderr_bytes=512, timeout=2).audit([{"a": 1}, {"a": 2}])
        self.assertEqual(audit.status, "inconclusive")
        self.assertIn("stderr exceeded 512 bytes", audit.reason)

    def test_timeout_returns_inconclusive(self):
        target = [sys.executable, "-c", "import time; time.sleep(5)"]
        audit = OrderAuditor(target, timeout=0.1).audit([{"a": 1}, {"a": 2}])
        self.assertEqual(audit.status, "inconclusive")
        self.assertIn("timed out", audit.reason)

    def test_overall_runtime_budget_is_respected(self):
        target = [sys.executable, "-c", "import time; time.sleep(5)"]
        audit = OrderAuditor(target, timeout=10, max_total_seconds=0.12).audit([{"a": 1}, {"a": 2}])
        self.assertEqual(audit.status, "inconclusive")
        self.assertLess(audit.executions, 3)

    def test_normal_small_utf8_response(self):
        target = [sys.executable, "-c", "import sys; sys.stdout.write('{\"name\":\"Русе\"}\\n')"]
        audit = OrderAuditor(target, max_output_bytes=512).audit([{"a": 1}, {"a": 2}], trials=1)
        self.assertEqual(audit.status, "no_difference_observed", audit.reason)


if __name__ == "__main__":
    unittest.main()
