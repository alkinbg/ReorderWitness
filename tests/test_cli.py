from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from reorderwitness.cli import main

ROOT = Path(__file__).resolve().parents[1]


class TestCli(unittest.TestCase):
    def test_buggy_case_writes_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "witness"
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = main(["--input", str(ROOT / "examples/two-records.jsonl"), "--output-dir", str(output_dir), "--trials", "1", "--", sys.executable, str(ROOT / "examples/processor_broken.py")])
            self.assertEqual(code, 1, buffer.getvalue())
            self.assertIn("DIFFERENCE", buffer.getvalue())
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["witness_record_count"], 2)
            self.assertIn("difference", report)
            for name in ("original-order.jsonl", "reordered-input.jsonl", "original-output.jsonl", "reordered-output.jsonl"):
                self.assertTrue((output_dir / name).exists(), name)

    def test_correct_case_returns_zero_without_creating_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "witness"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--input", str(ROOT / "examples/two-records.jsonl"), "--output-dir", str(output_dir), "--trials", "1", "--", sys.executable, str(ROOT / "examples/processor_correct.py")])
            self.assertEqual(code, 0)
            self.assertFalse(output_dir.exists())

    def test_existing_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "exists"
            dest.mkdir()
            (dest / "sentinel.txt").write_text("keep", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--input", str(ROOT / "examples/two-records.jsonl"), "--output-dir", str(dest), "--trials", "1", "--", sys.executable, str(ROOT / "examples/processor_broken.py")])
            self.assertEqual(code, 2)
            self.assertEqual((dest / "sentinel.txt").read_text(encoding="utf-8"), "keep")

    def test_input_byte_limit_prevents_starting_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stderr(io.StringIO()) as captured:
                code = main([
                    "--input", str(ROOT / "examples/two-records.jsonl"),
                    "--max-input-bytes", "5", "--", sys.executable,
                    str(ROOT / "examples/processor_broken.py"),
                ])
            self.assertEqual(code, 2)
            self.assertIn("input file exceeds 5 bytes", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
