from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from research_team.models import Paper
from research_team.tools import (
    arxiv_search,
    build_arxiv_queries,
    filter_relevant_papers,
    parse_arxiv_response,
    score_paper_relevance,
)


class ToolTests(unittest.TestCase):
    def test_agent_memory_topic_builds_precise_queries(self) -> None:
        queries = build_arxiv_queries("近年来Agent Memory有哪些研究方向？")

        self.assertIn('all:"agent memory"', queries)
        self.assertTrue(any("LLM agent" in query for query in queries))

    def test_parse_arxiv_response_extracts_metadata(self) -> None:
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/1234.5678v1</id>
            <title>Graph-based Agent Memory</title>
            <summary>Agent memory taxonomy and applications.</summary>
            <published>2026-02-05T00:00:00Z</published>
            <author><name>Alice</name></author>
            <link title="pdf" href="http://arxiv.org/pdf/1234.5678v1"/>
          </entry>
        </feed>
        """

        papers = parse_arxiv_response(xml)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].year, "2026")
        self.assertEqual(papers[0].authors, ["Alice"])
        self.assertIn("Graph-based Agent Memory", papers[0].title)

    def test_relevance_filter_keeps_agent_memory_and_rejects_physics(self) -> None:
        relevant = score_paper_relevance(
            Paper(
                title="Graph-based Agent Memory: Taxonomy, Techniques, and Applications",
                authors=[],
                year="2026",
                summary="This paper surveys long-term memory and retrieval for LLM agents.",
                url="https://arxiv.org/abs/1",
            ),
            "Agent Memory",
        )
        physics = score_paper_relevance(
            Paper(
                title="Observation of electroweak production of pairs of Z bosons",
                authors=[],
                year="2026",
                summary="Proton-proton collision evidence in the final state.",
                url="https://arxiv.org/abs/2",
            ),
            "Agent Memory",
        )

        accepted, rejected = filter_relevant_papers(
            [relevant, physics], max_results=5, min_relevance=3.0
        )

        self.assertEqual([paper.title for paper in accepted], [relevant.title])
        self.assertEqual(rejected[0]["title"], physics.title)
        self.assertLess(physics.relevance_score, 3.0)

    def test_candidate_pool_zero_uses_offline_fallback(self) -> None:
        papers, warnings, rejected, queries = arxiv_search(
            "Agent Memory", max_results=2, candidate_pool=0
        )

        self.assertEqual(len(papers), 2)
        self.assertEqual(rejected, [])
        self.assertTrue(queries)
        self.assertIn("fallback", warnings[0])


if __name__ == "__main__":
    unittest.main()
