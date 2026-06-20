from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from research_team.memory import LongTermMemory, run_fingerprint


class MemoryTests(unittest.TestCase):
    def test_run_fingerprint_is_stable_for_same_papers(self) -> None:
        left = run_fingerprint(
            "Agent Memory",
            [{"url": "b"}, {"url": "a"}],
        )
        right = run_fingerprint(
            "agent   memory",
            [{"url": "a"}, {"url": "b"}],
        )

        self.assertEqual(left, right)

    def test_add_run_deduplicates_same_topic_and_papers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "memory.json"
            memory = LongTermMemory(path)
            papers = [{"title": "Graph-based Agent Memory", "year": "2026", "url": "u"}]
            analyses = [{"tags": ["agent-memory"]}]

            memory.add_run("Agent Memory", papers, analyses, "first.md")
            memory.add_run("Agent Memory", papers, analyses, "second.md")

            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["report_path"], "second.md")


if __name__ == "__main__":
    unittest.main()
