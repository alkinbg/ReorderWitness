"""Independent black-box example: graph components are invariant to edge order."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

from reorderwitness.core import OrderAuditor, parse_jsonl, canonical_bag

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "examples" / "graph-components"
EDGES = parse_jsonl((SCENARIO / "edges.jsonl").read_text(encoding="utf-8"), label="edges.jsonl")


class TestGraphComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def audit(program: str):
            return OrderAuditor(
                [sys.executable, str(SCENARIO / program)],
                timeout=5,
                max_executions=100,
            ).audit(EDGES, trials=8, seed=42)

        cls.broken = audit("processor_broken.py")
        cls.correct = audit("processor_correct.py")

    def test_broken_one_pass_graph_processor_is_order_sensitive(self):
        self.assertEqual(self.broken.status, "difference", self.broken.reason)
        self.assertIsNotNone(self.broken.witness)
        self.assertTrue(self.broken.witness.diff()["only_in_original_order"])
        self.assertTrue(self.broken.witness.diff()["only_in_reordered_input"])

    def test_witness_shrinks_to_two_edges_without_changing_input_multiset(self):
        self.assertEqual(self.broken.status, "difference", self.broken.reason)
        self.assertTrue(self.broken.minimization_complete)
        witness = self.broken.witness
        self.assertEqual(len(witness.baseline_input), 2)
        self.assertEqual(canonical_bag(witness.baseline_input), canonical_bag(witness.reordered_input))
        # Two connected edges are sufficient to demonstrate the broken algorithm.
        edges = [(e["u"], e["v"]) for e in witness.baseline_input]
        self.assertEqual(len({vertex for edge in edges for vertex in edge}), 3)

    def test_union_find_graph_processor_is_order_invariant(self):
        self.assertEqual(self.correct.status, "no_difference_observed", self.correct.reason)


if __name__ == "__main__":
    unittest.main()
