from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research_team.agents import (
    ReadingAgent,
    analysis_off_topic,
    build_fallback_critique,
)
from research_team.memory import LongTermMemory
from research_team.models import Paper
from research_team.tools import (
    arxiv_search,
    build_arxiv_queries,
    normalize_arxiv_query,
    score_paper_relevance,
)


XIAGUANG_TOPIC = "\u6709\u6ca1\u6709\u5173\u4e8e\u971e\u5149\u7684\u5177\u4f53\u7814\u7a76\uff1f"
AGENT_MEMORY_TOPIC = "Agent Memory \u7684\u957f\u671f\u8bb0\u5fc6\u7814\u7a76\u65b9\u5411\u6709\u54ea\u4e9b\uff1f"


class TopicGuardrailTests(unittest.TestCase):
    def test_chinese_atmospheric_topic_does_not_become_agent_query(self) -> None:
        normalized = normalize_arxiv_query(XIAGUANG_TOPIC)
        queries = " ".join(build_arxiv_queries(XIAGUANG_TOPIC)).lower()

        self.assertIn("twilight", normalized)
        self.assertIn("sky", normalized)
        self.assertNotIn("large language model agent", queries)
        self.assertNotIn("agent memory", queries)

    def test_agent_memory_detection_handles_mixed_language_without_overmatching(self) -> None:
        self.assertIn(
            "agent memory",
            normalize_arxiv_query("\u667a\u80fd\u4f53 memory \u7684\u7814\u7a76\u65b9\u5411"),
        )
        self.assertIn(
            "agent memory",
            normalize_arxiv_query("Agent \u8bb0\u5fc6\u6709\u54ea\u4e9b\u7814\u7a76"),
        )
        self.assertNotIn(
            "agent memory",
            normalize_arxiv_query("\u4eba\u5de5\u667a\u80fd\u6709\u54ea\u4e9b\u7814\u7a76\u65b9\u5411"),
        )

    def test_non_agent_topic_has_no_agent_memory_offline_fallback(self) -> None:
        papers, warnings, rejected, queries = arxiv_search(
            topic=XIAGUANG_TOPIC,
            max_results=3,
            candidate_pool=0,
            min_relevance=3.0,
        )

        self.assertEqual([], papers)
        self.assertEqual([], rejected)
        self.assertTrue(any("only available for Agent Memory" in item for item in warnings))
        self.assertNotIn("agent memory", " ".join(queries).lower())

        fallback_papers, _, _, _ = arxiv_search(
            topic=AGENT_MEMORY_TOPIC,
            max_results=2,
            candidate_pool=0,
            min_relevance=3.0,
        )
        self.assertEqual(2, len(fallback_papers))
        self.assertIn("Memory", fallback_papers[0].title)

    def test_relevance_scoring_is_topic_specific(self) -> None:
        atmospheric_paper = Paper(
            title="Effects Of Aerosol And Multiple Scattering On The Polarization Of The Twilight Sky",
            authors=[],
            year="2024",
            summary=(
                "Twilight sky observations quantify aerosol, atmospheric scattering, "
                "sky brightness, and polarization."
            ),
            url="https://example.test/twilight",
        )
        off_topic_agent_memory_paper = Paper(
            title="A Survey on the Memory Mechanism of Large Language Model based Agents",
            authors=[],
            year="2024",
            summary=(
                "This survey summarizes memory modules for LLM agents, retrieval, "
                "reflection, and consolidation."
            ),
            url="https://example.test/agent-memory",
        )
        on_topic_agent_memory_paper = Paper(
            title="A Survey on the Memory Mechanism of Large Language Model based Agents",
            authors=[],
            year="2024",
            summary=(
                "This survey summarizes memory modules for LLM agents, retrieval, "
                "reflection, and consolidation."
            ),
            url="https://example.test/agent-memory",
        )

        atmospheric_score = score_paper_relevance(atmospheric_paper, XIAGUANG_TOPIC)
        off_topic_score = score_paper_relevance(
            off_topic_agent_memory_paper, XIAGUANG_TOPIC
        )
        agent_topic_score = score_paper_relevance(
            on_topic_agent_memory_paper, AGENT_MEMORY_TOPIC
        )

        self.assertGreaterEqual(atmospheric_score.relevance_score, 3.0)
        self.assertLess(off_topic_score.relevance_score, 3.0)
        self.assertGreaterEqual(agent_topic_score.relevance_score, 3.0)

    def test_fallback_analysis_uses_topic_specific_categories(self) -> None:
        paper = Paper(
            title="Aerosol parameters for night sky brightness modelling estimated from daytime sky images",
            authors=[],
            year="2024",
            summary=(
                "The study estimates aerosol parameters for sky brightness and skyglow "
                "modelling from sky observations."
            ),
            url="https://example.test/skyglow",
            relevance_score=5.0,
        )

        analysis = ReadingAgent()._fallback_analyze_paper(
            paper.to_dict(), XIAGUANG_TOPIC
        )

        self.assertNotIn("agent-memory", analysis.tags)
        self.assertNotIn("long-term-memory", analysis.tags)
        self.assertNotIn("LLM-agent memory", analysis.method)
        self.assertIn(analysis.category, {"\u5929\u7a7a\u4eae\u5ea6\u4e0e\u5149\u6c61\u67d3", "\u6c14\u6eb6\u80f6\u3001\u6563\u5c04\u4e0e\u504f\u632f\u89c2\u6d4b"})

    def test_off_topic_llm_analysis_is_rejected_for_non_agent_topics(self) -> None:
        self.assertTrue(
            analysis_off_topic(
                {
                    "category": "\u957f\u671f\u8bb0\u5fc6\u67b6\u6784",
                    "method": "LLM-agent memory mechanism analysis.",
                    "contribution": "agent memory survey",
                    "tags": ["agent-memory"],
                },
                XIAGUANG_TOPIC,
            )
        )
        self.assertFalse(
            analysis_off_topic(
                {
                    "category": "\u957f\u671f\u8bb0\u5fc6\u67b6\u6784",
                    "method": "LLM-agent memory mechanism analysis.",
                    "contribution": "agent memory survey",
                    "tags": ["agent-memory"],
                },
                AGENT_MEMORY_TOPIC,
            )
        )

    def test_memory_retrieval_requires_evidence_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "memory.json"
            memory_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "bad-topic-overlap",
                            "topic": XIAGUANG_TOPIC,
                            "papers": [
                                {
                                    "title": "A Survey on the Memory Mechanism of Large Language Model based Agents",
                                    "year": "2024",
                                    "url": "https://example.test/agent-memory",
                                }
                            ],
                            "tags": ["agent-memory"],
                            "report_path": "bad.md",
                        },
                        {
                            "id": "good-evidence-overlap",
                            "topic": "\u5927\u6c14\u5149\u5b66\u6587\u732e",
                            "papers": [
                                {
                                    "title": "Twilight sky aerosol polarization observations",
                                    "year": "2024",
                                    "url": "https://example.test/twilight",
                                }
                            ],
                            "tags": ["twilight-sky", "aerosol", "polarization"],
                            "report_path": "good.md",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            results = LongTermMemory(memory_path).retrieve(XIAGUANG_TOPIC)

        self.assertEqual(["good-evidence-overlap"], [item["id"] for item in results])

    def test_generic_fallback_critique_does_not_leak_agent_memory_template(self) -> None:
        critique = build_fallback_critique(
            {
                "topic": "\u86cb\u767d\u8d28\u8bbe\u8ba1\u6709\u54ea\u4e9b\u65b9\u6cd5\uff1f",
                "paper_analyses": [{"title": "paper"}],
            }
        )

        self.assertNotIn("\u957f\u671f\u8bb0\u5fc6", critique)
        self.assertNotIn("\u9690\u79c1", critique)
        self.assertIn("\u53ef\u590d\u73b0\u6027", critique)


if __name__ == "__main__":
    unittest.main()
