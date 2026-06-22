"""Smoke tests for the v2 upgrades (semantic/procedural memory, extra tools,
WriterAgent LLM authoring, parallel reading, checkpointer).

Run with:
    cd code
    .venv\\Scripts\\python -m unittest tests.test_upgrades_v2 -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import research_team.tools as tools
from research_team.agents import (
    CriticAgent,
    ManagerAgent,
    ReadingAgent,
    SearchAgent,
    WriterAgent,
    _format_memory_hint_for_prompt,
)
from research_team.llm import MockResearchLLM
from research_team.memory import ProceduralMemory, SemanticMemory
from research_team.models import Paper
from research_team.tools import (
    citation_graph,
    math_calc,
    query_rewrite_llm,
    score_paper_relevance,
)
from research_team.workflow import _build_checkpointer

CORDYCEPS = "我现在要研究虫草菌"


class MemoryHintTests(unittest.TestCase):
    def test_hint_renders_three_memory_types(self) -> None:
        state = {
            "retrieved_memories": [
                {"topic": "Cordyceps 2024", "score": 0.5, "tags": ["t"], "papers": [{"title": "X"}]}
            ],
            "semantic_memory": {
                "directions": ["基础研究", "应用"],
                "common_methods": ["abstract analysis"],
                "known_limitations": ["仅基于摘要"],
            },
            "procedural_memory": {"effective_queries": ["q1", "q2"]},
        }
        hint = _format_memory_hint_for_prompt(state)
        self.assertIn("Episodic", hint)
        self.assertIn("Semantic", hint)
        self.assertIn("Procedural", hint)


class SemanticMemoryTests(unittest.TestCase):
    def test_update_and_retrieve(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mem = SemanticMemory(Path(td) / "sem.json")
            mem.update_from_run(
                domain="life-science",
                topic_profile={"expected_directions": ["基础研究", "应用"]},
                analyses=[{"method": "abstract analysis", "limitations": "仅基于摘要"}],
                critique="可复现性不足。统计效力欠缺。",
            )
            out = mem.retrieve("life-science")
            self.assertIn("基础研究", out["directions"])
            self.assertIn("abstract analysis", out["common_methods"])
            self.assertTrue(out["known_limitations"])


class ProceduralMemoryTests(unittest.TestCase):
    def test_record_and_rank_by_hit_rate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mem = ProceduralMemory(Path(td) / "pro.json")
            mem.record_search(domain="life-science", queries=["q1", "q2"], paper_count=2)
            mem.record_search(domain="life-science", queries=["q1", "q3"], paper_count=0)
            out = mem.retrieve("life-science")
            self.assertIn("q1", out["effective_queries"])
            self.assertIn("q2", out["effective_queries"])
            self.assertNotIn("q3", out["effective_queries"])


class MathCalcTests(unittest.TestCase):
    def test_basic_eval(self) -> None:
        r = math_calc("round(sum([1,2,3,4])/4, 2)")
        self.assertEqual(r["result"], 2.5)
        self.assertEqual(r["error"], "")

    def test_forbidden_token_is_rejected(self) -> None:
        r = math_calc("__import__('os').system('ls')")
        self.assertIsNone(r["result"])
        self.assertNotEqual(r["error"], "")


class QueryRewriteTests(unittest.TestCase):
    def test_llm_returns_keywords(self) -> None:
        llm = MockResearchLLM()
        out = query_rewrite_llm(CORDYCEPS, ["cordyceps"], llm)
        self.assertTrue(out["keywords"])

    def test_no_llm_uses_fallback(self) -> None:
        out = query_rewrite_llm("topic", ["cordyceps"], None)
        self.assertTrue(out["keywords"])


class CitationGraphTests(unittest.TestCase):
    def test_offline_returns_marker(self) -> None:
        out = citation_graph(["A title"], timeout=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "A title")


class WriterLLMTests(unittest.TestCase):
    def test_writer_invokes_llm_for_four_sections(self) -> None:
        llm = MockResearchLLM()
        state = {
            "topic": CORDYCEPS,
            "papers": [{"title": "P1", "year": "2024", "summary": "s", "relevance_score": 3}],
            "paper_analyses": [
                {
                    "title": "P1",
                    "category": "c",
                    "contribution": "x",
                    "method": "m",
                    "limitations": "l",
                    "tags": ["a"],
                }
            ],
            "critique_summary": "c",
            "llm_keywords": ["cordyceps"],
            "semantic_memory": {},
        }
        WriterAgent().run(state, llm)
        self.assertTrue(state.get("executive_summary"))
        self.assertTrue(state.get("direction_narratives"))
        self.assertTrue(state.get("future_work"))
        self.assertTrue(state.get("glossary"))


class FiveAgentLLMCoverageTests(unittest.TestCase):
    """Every agent invokes the LLM at least once in mock mode."""

    def test_all_five_agents_invoke_llm(self) -> None:
        llm = MockResearchLLM()
        # Augment mock to count invocations.
        original_invoke = llm.invoke
        counter = {"n": 0}

        def counting_invoke(system_prompt, user_prompt):
            counter["n"] += 1
            return original_invoke(system_prompt, user_prompt)

        llm.invoke = counting_invoke  # type: ignore[assignment]

        state = {"topic": CORDYCEPS, "max_papers": 2, "candidate_pool": 20, "min_relevance": 2.0}
        ManagerAgent().run(state, llm)
        n_manager = counter["n"]

        cands = [
            Paper(
                title="Cordyceps survey",
                authors=[],
                year="2025",
                summary="cordyceps review.",
                url="a",
                source="arxiv",
            )
        ]

        def fake_arxiv(topic, queries, max_results, timeout, candidate_pool, sort_by, extra_keywords=None):
            return [score_paper_relevance(c, topic, extra_keywords) for c in cands], []

        def fake_pubmed(topic, queries, timeout, candidate_pool, extra_keywords=None):
            return [], []

        with patch.object(tools, "fetch_arxiv_candidates", side_effect=fake_arxiv), patch.object(
            tools, "pubmed_search", side_effect=fake_pubmed
        ):
            SearchAgent().run(state, llm)
        n_search = counter["n"]

        ReadingAgent().run(state, llm)
        n_reading = counter["n"]

        CriticAgent().run(state, llm)
        n_critic = counter["n"]

        WriterAgent().run(state, llm)
        n_writer = counter["n"]

        self.assertGreater(n_manager, 0, "Manager should call LLM at least once.")
        self.assertGreater(n_search, n_manager, "Search should call LLM at least once.")
        self.assertGreater(n_reading, n_search, "Reading should call LLM at least once.")
        self.assertGreater(n_critic, n_reading, "Critic should call LLM at least once.")
        self.assertGreaterEqual(n_writer - n_critic, 4, "Writer should call LLM 4 times.")


class CriticEvidenceTests(unittest.TestCase):
    def test_gather_evidence_populates_calc_logs(self) -> None:
        llm = MockResearchLLM()
        state = {
            "topic": CORDYCEPS,
            "papers": [{"title": "P", "relevance_score": 4.0}],
            "paper_analyses": [{"title": "P"}],
            "llm_keywords": ["cordyceps"],
        }
        CriticAgent().run(state, llm)
        self.assertTrue(state.get("calc_logs"))
        self.assertGreaterEqual(len(state["calc_logs"]), 2)


class CheckpointerTests(unittest.TestCase):
    def test_build_checkpointer_returns_object_or_none(self) -> None:
        cp = _build_checkpointer({})
        self.assertTrue(cp is None or hasattr(cp, "put") or hasattr(cp, "get"))


class ReadingParallelTests(unittest.TestCase):
    def test_parallel_preserves_order_and_count(self) -> None:
        llm = MockResearchLLM()
        state = {
            "topic": CORDYCEPS,
            "papers": [
                {"title": f"P{i}", "year": "2024", "summary": "s", "relevance_score": 3}
                for i in range(5)
            ],
        }
        ReadingAgent().run(state, llm)
        analyses = state["paper_analyses"]
        self.assertEqual(len(analyses), 5)
        self.assertEqual([a["title"] for a in analyses], [f"P{i}" for i in range(5)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
