"""Order invariance contract for a JSONL aggregator using itertools.groupby."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

from reorderwitness.core import OrderAuditor, canonical_bag, parse_jsonl


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "groupby"
RECORDS = parse_jsonl(
    (EXAMPLE / "records.jsonl").read_text(encoding="utf-8"),
    label="groupby records",
)


class TestGroupbyScenario(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        def audit(script: str):
            return OrderAuditor(
                [sys.executable, str(EXAMPLE / script)],
                timeout=5,
                max_executions=100,
            ).audit(RECORDS, trials=30, seed=42)

        cls.broken = audit("processor_broken.py")
        cls.correct = audit("processor_correct.py")

    def test_unsorted_groupby_misuse_changes_aggregation(self) -> None:
        self.assertEqual(self.broken.status, "difference", self.broken.reason)
        self.assertIsNotNone(self.broken.witness)

    def test_three_records_are_required_for_this_witness(self) -> None:
        witness = self.broken.witness
        self.assertIsNotNone(witness)
        self.assertEqual(len(witness.baseline_input), 3)
        self.assertTrue(self.broken.minimization_complete)
        self.assertEqual(
            canonical_bag(witness.baseline_input),
            canonical_bag(witness.reordered_input),
        )
        self.assertTrue(witness.diff()["only_in_original_order"])
        self.assertTrue(witness.diff()["only_in_reordered_input"])

    def test_defaultdict_aggregation_is_not_flagged(self) -> None:
        self.assertEqual(self.correct.status, "no_difference_observed", self.correct.reason)


if __name__ == "__main__":
    unittest.main()
