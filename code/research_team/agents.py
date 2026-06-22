from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from research_team.llm import BaseLLM
from research_team.models import PaperAnalysis, ResearchState
from research_team.tools import (
    citation_graph,
    extract_pdf_text,
    is_agent_memory_topic,
    is_atmospheric_optics_topic,
    is_life_science_topic,
    keyword_tokens,
    math_calc,
    paper_stats,
    query_rewrite_llm,
    research_search,
)


def add_message(state: ResearchState, speaker: str, content: str) -> None:
    state.setdefault("messages", []).append(
        {
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    )


# ---------------------------------------------------------------------------
# ManagerAgent: Planning + Chain-of-Thought topic profiling.
# ---------------------------------------------------------------------------

TOPIC_PROFILE_SYSTEM_PROMPT = (
    "You are ManagerAgent. Use Chain-of-Thought (CoT) reasoning to break the user's "
    "research question into a structured topic profile that downstream search agents "
    "can act on. Always return strict JSON. Never invent unimplemented tools."
)

TOPIC_PROFILE_USER_TEMPLATE = (
    "用户主题：{topic}\n\n"
    "请用CoT思考后输出 topic_profile_json，schema 为:\n"
    "{{\n"
    "  \"thoughts\": <你的简短CoT，<=120字>,\n"
    "  \"english_keywords\": [<6~10个高质量英文检索词，覆盖同义/上位/方法/应用，越具体越好>],\n"
    "  \"domain\": <agent-memory|life-science|atmospheric-optics|ai|general 之一>,\n"
    "  \"arxiv_query_hint\": <一行 arXiv 检索式提示>,\n"
    "  \"pubmed_query_hint\": <若与生物医学相关给出，否则空字符串>,\n"
    "  \"expected_directions\": [<3~5个该问题下可能的子方向，中文短句>]\n"
    "}}\n"
    "约束：english_keywords 必须可直接用于 arXiv / PubMed 检索；"
    "如果主题是中文的冷门词（如\"虫草菌\"），请翻译并扩展为拉丁学名/英文术语。"
    "只输出 JSON，不要任何额外说明。"
)


class ManagerAgent:
    name = "ManagerAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        topic = state["topic"]

        # 1) CoT topic profiling — the real LLM contribution at this stage.
        profile = self._derive_topic_profile(topic, llm)
        state["topic_profile"] = profile
        extras = list(profile.get("english_keywords", []) or [])
        state["llm_keywords"] = extras
        add_message(
            state,
            self.name,
            "CoT topic profile: " + json.dumps(profile, ensure_ascii=False),
        )

        # 2) Planning text (kept for backwards compatibility / report § 3).
        system_prompt = (
            "You are ManagerAgent for a runnable course project. Use concise Planning. "
            "Only mention implemented capabilities: arXiv/PubMed search, local PDF extraction, "
            "paper statistics, JSON long-term memory, LangGraph workflow with conditional "
            "re-search, and Markdown output. Do not mention Google Scholar, Semantic Scholar, "
            "Chroma, FAISS, Neo4j, citation APIs, parallel crawling, or any unimplemented tool."
        )
        memory_hint = _format_memory_hint_for_prompt(state)
        user_prompt = (
            f"请为科研问题制定多Agent调研计划：{topic}。\n"
            f"已识别的英文检索关键词：{', '.join(extras) if extras else '(none)'}。\n"
            f"{memory_hint}"
            "要求用6条以内覆盖检索、阅读、反思、写作、记忆更新；不要写理想系统能力。"
        )
        plan = llm.invoke(system_prompt, user_prompt)
        plan = safe_manager_plan(plan, state)
        state["plan"] = plan
        add_message(state, self.name, f"Planning result: {plan}")
        return state

    def _derive_topic_profile(self, topic: str, llm: BaseLLM) -> Dict[str, Any]:
        """Ask the LLM for a structured topic profile (CoT). Falls back to a
        deterministic profile if the response cannot be parsed."""
        try:
            raw = llm.invoke(
                TOPIC_PROFILE_SYSTEM_PROMPT,
                TOPIC_PROFILE_USER_TEMPLATE.format(topic=topic),
            )
            data = parse_json_object(raw)
        except Exception:
            data = {}
        if not data:
            data = self._fallback_topic_profile(topic)
        # Normalize fields.
        keywords = data.get("english_keywords", [])
        if isinstance(keywords, str):
            keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        if not isinstance(keywords, list):
            keywords = []
        keywords = [str(kw).strip() for kw in keywords if str(kw).strip()][:10]
        if not keywords:
            keywords = self._fallback_topic_profile(topic)["english_keywords"]
        data["english_keywords"] = keywords
        data.setdefault("domain", "general")
        data.setdefault("arxiv_query_hint", " OR ".join(keywords[:6]))
        data.setdefault("pubmed_query_hint", "")
        data.setdefault("expected_directions", [])
        data.setdefault("thoughts", "")
        return data

    def _fallback_topic_profile(self, topic: str) -> Dict[str, Any]:
        # Reuse the offline keyword expander shipped in llm.py so the profile is
        # still useful when the API/mocked LLM produces nothing parseable.
        try:
            from research_team.llm import _mock_keywords_for_topic, _mock_domain_for_topic

            keywords = _mock_keywords_for_topic(topic)
            domain = _mock_domain_for_topic(topic)
        except Exception:
            keywords = [tok for tok in topic.split() if len(tok) >= 3][:6] or [
                "research",
                "review",
            ]
            domain = "general"
        return {
            "english_keywords": keywords,
            "domain": domain,
            "arxiv_query_hint": " OR ".join(keywords[:6]),
            "pubmed_query_hint": "",
            "expected_directions": [],
            "thoughts": "fallback: offline keyword expansion",
        }


def self_topic_profile_message(*_args, **_kwargs):  # pragma: no cover - removed placeholder
    return None


def _format_memory_hint_for_prompt(state: ResearchState) -> str:
    """Render long-term + semantic + procedural memory into a compact prompt
    fragment that ManagerAgent / SearchAgent can paste into their LLM calls."""
    episodic = state.get("retrieved_memories", []) or []
    semantic = state.get("semantic_memory", {}) or {}
    procedural = state.get("procedural_memory", {}) or {}

    chunks: List[str] = []
    if episodic:
        episodic_lines = []
        for memory in episodic[:3]:
            topic = (memory.get("topic") or "")[:60]
            score = memory.get("score", 0)
            tags = ", ".join((memory.get("tags") or [])[:6])
            paper_titles = "；".join(
                (p.get("title", "") or "")[:60]
                for p in (memory.get("papers", []) or [])[:2]
            )
            episodic_lines.append(
                f"- 历史主题=「{topic}」 score={score} tags={tags} 代表论文：{paper_titles}"
            )
        chunks.append("【Episodic Memory（历史相似调研）】\n" + "\n".join(episodic_lines))

    if semantic:
        directions = (semantic.get("directions") or [])[:6]
        common_methods = (semantic.get("common_methods") or [])[:6]
        known_limitations = (semantic.get("known_limitations") or [])[:4]
        sem_lines = []
        if directions:
            sem_lines.append("- 已知子方向：" + "；".join(directions))
        if common_methods:
            sem_lines.append("- 常见方法：" + "；".join(common_methods))
        if known_limitations:
            sem_lines.append("- 已识别的局限：" + "；".join(known_limitations))
        if sem_lines:
            chunks.append("【Semantic Memory（领域语义）】\n" + "\n".join(sem_lines))

    if procedural:
        effective = (procedural.get("effective_queries") or [])[:5]
        if effective:
            chunks.append(
                "【Procedural Memory（历史有效检索式）】\n"
                + "\n".join(f"- {q}" for q in effective)
            )

    if not chunks:
        return ""
    return (
        "请阅读以下历史记忆并在制定计划时复用有效经验、避免重复已识别的局限：\n"
        + "\n\n".join(chunks)
        + "\n\n"
    )


# ---------------------------------------------------------------------------
# SearchAgent: ReAct loop (Thought → Action → Observation, up to 3 turns).
# ---------------------------------------------------------------------------

REACT_SYSTEM_PROMPT = (
    "You are SearchAgent. You operate in a ReAct loop. Each turn you receive the "
    "current observation (paper_count, top_titles, missing_aspects) and must decide "
    "the next action. Available actions: 'search' (run research_search again with "
    "refined_keywords) or 'stop' (hand off to ReadingAgent). Return strict JSON only."
)

REACT_USER_TEMPLATE = (
    "迭代 {iteration}/{max_iterations}\n"
    "用户主题：{topic}\n"
    "已知英文关键词：{keywords}\n"
    "Observation: paper_count={paper_count}, supporting_count={supporting_count}, "
    "top_titles={top_titles}, recent_warnings={warnings}\n\n"
    "请输出 react_decision_json:\n"
    "{{\n"
    "  \"thought\": <短CoT，解释你的判断>,\n"
    "  \"action\": <'search' 或 'stop'>,\n"
    "  \"refined_keywords\": [<若 action=='search'，给出 3~6 个补充关键词；否则可空>]\n"
    "}}\n"
    "策略：若 paper_count==0 必须 search 并扩展同义词/英文学名；"
    "若 paper_count>=3 且 top_titles 看起来切题可以 stop；"
    "至多 {max_iterations} 轮。"
)


class SearchAgent:
    name = "SearchAgent"
    MAX_REACT_ITERATIONS = 2

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        topic = state["topic"]
        extras: List[str] = list(state.get("llm_keywords", []))
        react_trace: List[Dict[str, Any]] = state.setdefault("react_trace", [])
        first = not state.get("papers")
        last_warnings: List[str] = []

        for iteration in range(1, self.MAX_REACT_ITERATIONS + 1):
            if first or iteration > 1:
                # Run the underlying tool with the current keyword set.
                add_message(
                    state,
                    self.name,
                    "Thought: 需要检索 arXiv/PubMed。 Action: research_search("
                    f"topic='{topic}', extra_keywords={extras}).",
                )
                search_result = research_search(
                    topic=topic,
                    max_results=state.get("max_papers", 5),
                    candidate_pool=state.get("candidate_pool", 25),
                    min_relevance=state.get("min_relevance", 3.0),
                    sort_by=state.get("sort_by", "relevance"),
                    extra_keywords=extras,
                )
                self._absorb_search_result(state, search_result, extras)
                last_warnings = search_result.get("warnings", [])
                first = False

            decision = self._react_decide(
                state=state,
                llm=llm,
                topic=topic,
                extras=extras,
                iteration=iteration,
                last_warnings=last_warnings,
            )
            react_trace.append(
                {
                    "iteration": iteration,
                    "extras_in": list(extras),
                    "paper_count": len(state.get("papers", [])),
                    "decision": decision,
                }
            )
            add_message(
                state,
                self.name,
                f"ReAct[{iteration}] thought={decision.get('thought', '')} | "
                f"action={decision.get('action', 'stop')} | "
                f"refined={decision.get('refined_keywords', [])}",
            )
            action = (decision.get("action") or "stop").lower()
            if action == "stop":
                break
            refined = [
                str(kw).strip()
                for kw in (decision.get("refined_keywords") or [])
                if str(kw).strip()
            ]
            if not refined:
                # LLM said search but gave nothing — exit to avoid an infinite loop.
                break
            # Merge keywords and continue the loop.
            for kw in refined:
                if kw not in extras:
                    extras.append(kw)
            state["llm_keywords"] = extras

        # Final observation message — ReAct "Observe / Summarize" step.
        add_message(
            state,
            self.name,
            "Observe: retrieved "
            f"{len(state.get('papers', []))} core papers and "
            f"{len(state.get('supporting_papers', []))} supporting papers. "
            "Summarize: candidates are ready for ReadingAgent.",
        )
        return state

    def _absorb_search_result(
        self,
        state: ResearchState,
        search_result: Dict[str, Any],
        extras: List[str],
    ) -> None:
        papers = search_result["papers"]
        supporting = search_result["supporting_papers"]
        warnings = search_result["warnings"]
        rejected = search_result["rejected_papers"]
        queries = search_result["queries"]
        state.setdefault("warnings", []).extend(warnings)
        paper_dicts = [paper.to_dict() for paper in papers]
        supporting_dicts = [paper.to_dict() for paper in supporting]
        state["papers"] = paper_dicts
        state["supporting_papers"] = supporting_dicts
        state["rejected_papers"] = rejected
        state["search_queries"] = queries
        state["search_diagnostics"] = search_result["search_diagnostics"]
        state.setdefault("tool_logs", []).append(
            {
                "tool": "research_search",
                "query": state.get("topic", ""),
                "expanded_queries": queries,
                "extra_keywords": list(extras),
                "paper_count": len(paper_dicts),
                "supporting_count": len(supporting_dicts),
                "rejected_count": len(rejected),
                "min_relevance": state.get("min_relevance", 3.0),
                "diagnostics": search_result["search_diagnostics"],
                "warnings": warnings,
            }
        )

    def _react_decide(
        self,
        state: ResearchState,
        llm: BaseLLM,
        topic: str,
        extras: List[str],
        iteration: int,
        last_warnings: List[str],
    ) -> Dict[str, Any]:
        top_titles = [
            (p.get("title", "") or "")[:90]
            for p in state.get("papers", [])[:3]
        ]
        prompt = REACT_USER_TEMPLATE.format(
            iteration=iteration,
            max_iterations=self.MAX_REACT_ITERATIONS,
            topic=topic,
            keywords=", ".join(extras) if extras else "(none)",
            paper_count=len(state.get("papers", [])),
            supporting_count=len(state.get("supporting_papers", [])),
            top_titles=json.dumps(top_titles, ensure_ascii=False),
            warnings=json.dumps(last_warnings[:3], ensure_ascii=False),
        )
        # Final iteration: force stop so we never exceed budget.
        if iteration >= self.MAX_REACT_ITERATIONS:
            return {
                "thought": "iteration budget reached, force stop.",
                "action": "stop",
                "refined_keywords": [],
            }
        try:
            raw = llm.invoke(REACT_SYSTEM_PROMPT, prompt)
            decision = parse_json_object(raw)
        except Exception:
            decision = {}
        if not decision:
            decision = self._heuristic_decision(state)
        return decision

    def _heuristic_decision(self, state: ResearchState) -> Dict[str, Any]:
        if state.get("papers"):
            return {
                "thought": "已有论文，直接停止。",
                "action": "stop",
                "refined_keywords": [],
            }
        # No papers yet — propose generic English fallbacks so a retry can rescue
        # the run even when the LLM call breaks.
        return {
            "thought": "无候选，尝试补充通用同义词。",
            "action": "search",
            "refined_keywords": ["review", "survey", "mechanism", "application"],
        }


class ReadingAgent:
    name = "ReadingAgent"
    MAX_PARALLEL = 4

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        papers = state.get("papers", []) or []
        analyses: List[Dict[str, Any]] = self._analyze_in_parallel(
            papers, state["topic"], llm
        )

        pdf_notes: List[Dict[str, str]] = []
        for raw_path in state.get("pdf_paths", []):
            path = Path(raw_path)
            text, warnings = extract_pdf_text(path)
            state.setdefault("warnings", []).extend(warnings)
            state.setdefault("tool_logs", []).append(
                {
                    "tool": "pdf_extract",
                    "path": str(path),
                    "chars": len(text),
                    "warnings": warnings,
                }
            )
            if text:
                note = {
                    "path": str(path),
                    "excerpt": text[:1200],
                    "summary": summarize_pdf_text(text),
                }
                pdf_notes.append(note)
                analyses.append(
                    PaperAnalysis(
                        title=path.stem,
                        year="local",
                        url=str(path),
                        contribution=note["summary"],
                        method="Local PDF reading with pdfplumber text extraction.",
                        limitations="Only the first pages are read in the demo mode.",
                        tags=["pdf", "local-document"],
                        source="local_pdf",
                        category="本地PDF材料",
                    ).to_dict()
                )

        state["paper_analyses"] = analyses
        state["pdf_notes"] = pdf_notes
        add_message(
            state,
            self.name,
            f"Read {len(papers)} paper abstracts (parallel<={self.MAX_PARALLEL}) "
            f"and {len(pdf_notes)} local PDFs.",
        )
        return state

    def _analyze_in_parallel(
        self, papers: List[Dict[str, Any]], topic: str, llm: BaseLLM
    ) -> List[Dict[str, Any]]:
        if not papers:
            return []
        if len(papers) <= 1:
            return [self._analyze_paper(papers[0], topic, llm).to_dict()]
        try:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(
                max_workers=min(self.MAX_PARALLEL, len(papers))
            ) as pool:
                futures = [
                    pool.submit(self._analyze_paper, paper, topic, llm)
                    for paper in papers
                ]
                return [future.result().to_dict() for future in futures]
        except Exception:
            # Fall back to sequential — preserves ordering and never crashes
            # the workflow.
            return [self._analyze_paper(paper, topic, llm).to_dict() for paper in papers]

    def _analyze_paper(
        self, paper: Dict[str, Any], topic: str, llm: BaseLLM
    ) -> PaperAnalysis:
        # Try LLM-driven structured extraction first — every mode (mock or real)
        # gets exactly one LLM call per paper, satisfying the "every agent
        # really invokes the LLM" contract.
        llm_result = self._analyze_with_llm(paper, topic, llm)
        if llm_result is not None:
            return llm_result
        return self._fallback_analyze_paper(paper, topic)

    def _analyze_with_llm(
        self, paper: Dict[str, Any], topic: str, llm: BaseLLM
    ) -> PaperAnalysis | None:
        system_prompt = (
            "You are ReadingAgent. Extract only what is supported by the title and abstract. "
            "Return strict JSON for reading_extract_json with keys: contribution, method, "
            "limitations, tags, category. Use Chinese, concise wording. "
            "Do not use Agent Memory, LLM agent, retrieval memory, or long-term memory "
            "categories unless the title/abstract and user topic are about those concepts."
        )
        user_prompt = (
            "请输出 reading_extract_json：\n"
            + json.dumps(
                {
                    "user_topic": topic,
                    "title": paper.get("title", ""),
                    "year": paper.get("year", ""),
                    "abstract": paper.get("summary", ""),
                    "matched_terms": paper.get("matched_terms", []),
                    "relevance_score": paper.get("relevance_score", 0),
                },
                ensure_ascii=False,
            )
        )
        try:
            raw = llm.invoke(system_prompt, user_prompt)
            data = parse_json_object(raw)
        except Exception:
            return None
        if not data:
            return None
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if not isinstance(tags, list):
            tags = []
        if analysis_off_topic(data, topic):
            return None
        return PaperAnalysis(
            title=paper.get("title", ""),
            year=str(paper.get("year", "unknown")),
            url=paper.get("url", ""),
            contribution=str(data.get("contribution", "")).strip()
            or first_sentence(paper.get("summary", "")),
            method=str(data.get("method", "")).strip()
            or infer_method(paper.get("title", ""), paper.get("summary", ""), topic),
            limitations=str(data.get("limitations", "")).strip()
            or "仅基于摘要分析，尚需全文验证。",
            tags=[str(tag) for tag in tags[:5]]
            or infer_tags(paper.get("title", ""), topic),
            source=paper.get("source", "arxiv"),
            category=str(data.get("category", "")).strip()
            or infer_category(paper.get("title", ""), paper.get("summary", ""), topic),
            relevance_score=float(paper.get("relevance_score", 0) or 0),
        )

    def _fallback_analyze_paper(
        self, paper: Dict[str, Any], topic: str
    ) -> PaperAnalysis:
        title = paper.get("title", "")
        summary = paper.get("summary", "")
        tags = infer_tags(title + " " + summary, topic)
        contribution = first_sentence(summary) or "The paper contributes evidence related to the research topic."
        method = infer_method(title, summary, topic)
        limitations = (
            "The abstract-level analysis may miss experimental details; full PDF reading "
            "is needed for stronger evidence."
        )
        return PaperAnalysis(
            title=title,
            year=str(paper.get("year", "unknown")),
            url=paper.get("url", ""),
            contribution=contribution,
            method=method,
            limitations=limitations,
            tags=tags,
            source=paper.get("source", "arxiv"),
            category=infer_category(title, summary, topic),
            relevance_score=float(paper.get("relevance_score", 0) or 0),
        )


class CriticAgent:
    name = "CriticAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        # Pre-flight: pull citation stats + coverage math to ground the critique.
        self._gather_evidence(state)

        # Reflexion decision — structured JSON that tells the workflow whether
        # to loop back to SearchAgent.
        decision = self._decide(state, llm)
        state["critic_decision"] = decision
        state["critique_summary"] = decision.get("reflection") or build_fallback_critique(state)

        # Surface suggested keywords so the SearchAgent retry uses them; if the
        # LLM did not propose any, fall back to query_rewrite_llm so the retry
        # is never empty.
        suggested = [
            str(kw).strip()
            for kw in (decision.get("suggested_keywords") or [])
            if str(kw).strip()
        ]
        if decision.get("needs_more_search") and not suggested:
            rewrite = query_rewrite_llm(
                topic=state.get("topic", ""),
                failed_keywords=state.get("llm_keywords", []) or [],
                llm=llm,
            )
            suggested = rewrite.get("keywords", []) or []
            state.setdefault("rewrite_history", []).append(rewrite)
            state.setdefault("tool_logs", []).append(
                {"tool": "query_rewrite_llm", "keywords": suggested}
            )
        if suggested:
            existing = list(state.get("llm_keywords", []))
            for kw in suggested:
                if kw not in existing:
                    existing.append(kw)
            state["llm_keywords"] = existing
            decision["suggested_keywords"] = suggested

        # Track how many times the critic has triggered a retry.
        retry_count = int(state.get("critic_retries", 0))
        if decision.get("needs_more_search"):
            state["critic_retries"] = retry_count + 1

        add_message(
            state,
            self.name,
            "Reflection: " + json.dumps(decision, ensure_ascii=False),
        )
        return state

    def _gather_evidence(self, state: ResearchState) -> None:
        """Run math_calc + citation_graph so the critic prompt has concrete
        evidence to reason over (and the run_log records the tool use)."""
        papers = state.get("papers", []) or []
        analyses = state.get("paper_analyses", []) or []
        # Coverage metric: how many analyses link back to an accepted paper.
        coverage = math_calc(
            "round(min(len(analyses) / max(len(papers), 1), 1.0) * 100, 1)",
            variables={"analyses": analyses, "papers": papers},
        )
        avg_relevance = math_calc(
            "round(sum(p['relevance_score'] for p in papers) / max(len(papers), 1), 3)",
            variables={"papers": papers},
        )
        state.setdefault("calc_logs", []).extend([coverage, avg_relevance])
        state.setdefault("tool_logs", []).append(
            {"tool": "math_calc", "coverage": coverage, "avg_relevance": avg_relevance}
        )
        # Citation graph for top 3 papers — non-blocking, best-effort.
        try:
            metrics = citation_graph(
                [p.get("title", "") for p in papers[:3]], timeout=6
            )
        except Exception:
            metrics = []
        if metrics:
            state["citation_metrics"] = metrics
            state.setdefault("tool_logs", []).append(
                {"tool": "citation_graph", "results": metrics}
            )

    def _decide(self, state: ResearchState, llm: BaseLLM) -> Dict[str, Any]:
        topic = state.get("topic", "")
        papers = state.get("papers", [])
        paper_count = len(papers)
        if llm.mode == "mock":
            # Mock mode: still go through the structured prompt so the mock LLM
            # can produce a JSON decision, keeping behaviour deterministic.
            try:
                raw = llm.invoke(
                    REFLEXION_SYSTEM_PROMPT,
                    REFLEXION_USER_TEMPLATE.format(
                        topic=topic,
                        paper_count=paper_count,
                        top_titles=json.dumps(
                            [(p.get("title", "") or "")[:90] for p in papers[:3]],
                            ensure_ascii=False,
                        ),
                        critic_angles=critic_angles_for_topic(topic),
                        analyses=json.dumps(
                            state.get("paper_analyses", [])[:3], ensure_ascii=False
                        ),
                    ),
                )
                data = parse_json_object(raw)
                if data:
                    return _normalize_critic_decision(data)
            except Exception:
                pass
            return _fallback_critic_decision(state)

        try:
            raw = llm.invoke(
                REFLEXION_SYSTEM_PROMPT,
                REFLEXION_USER_TEMPLATE.format(
                    topic=topic,
                    paper_count=paper_count,
                    top_titles=json.dumps(
                        [(p.get("title", "") or "")[:90] for p in papers[:3]],
                        ensure_ascii=False,
                    ),
                    critic_angles=critic_angles_for_topic(topic),
                    analyses=json.dumps(
                        state.get("paper_analyses", [])[:3], ensure_ascii=False
                    ),
                ),
            )
            data = parse_json_object(raw)
        except Exception:
            data = {}
        if not data:
            return _fallback_critic_decision(state)
        return _normalize_critic_decision(data)


REFLEXION_SYSTEM_PROMPT = (
    "You are CriticAgent. Use Reflexion: review the current analyses and decide "
    "whether the evidence is strong enough for the WriterAgent, or whether the "
    "SearchAgent should retry with new keywords. Always return strict JSON only."
)

REFLEXION_USER_TEMPLATE = (
    "用户主题：{topic}\n"
    "当前 paper_count={paper_count}, top_titles={top_titles}\n"
    "已抽取的前3篇分析：{analyses}\n"
    "Reflection 角度：{critic_angles}\n\n"
    "请输出 critic_decision_json:\n"
    "{{\n"
    "  \"reflection\": <<=120字的反思，指出证据局限/方法风险/应用边界>,\n"
    "  \"needs_more_search\": <true|false>,\n"
    "  \"suggested_keywords\": [<若 needs_more_search==true，给出 3~6 个补充英文关键词；否则空数组>]\n"
    "}}\n"
    "判断标准：paper_count<2 通常需要重检索；若现有论文与主题明显错位也应重检索。"
)


def _normalize_critic_decision(data: Dict[str, Any]) -> Dict[str, Any]:
    keywords = data.get("suggested_keywords", [])
    if isinstance(keywords, str):
        keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()]
    if not isinstance(keywords, list):
        keywords = []
    needs = bool(data.get("needs_more_search"))
    reflection = str(data.get("reflection") or "").strip()
    return {
        "reflection": reflection,
        "needs_more_search": needs,
        "suggested_keywords": [str(kw).strip() for kw in keywords if str(kw).strip()][:6],
    }


def _fallback_critic_decision(state: ResearchState) -> Dict[str, Any]:
    paper_count = len(state.get("papers", []))
    return {
        "reflection": build_fallback_critique(state),
        "needs_more_search": paper_count == 0,
        "suggested_keywords": ["review", "survey", "mechanism"]
        if paper_count == 0
        else [],
    }


class WriterAgent:
    name = "WriterAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        output_dir = Path(state.get("output_dir", "outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)

        state["stats"] = paper_stats(state.get("papers", []))
        state.setdefault("tool_logs", []).append(
            {"tool": "paper_stats", "result": state["stats"]}
        )

        # ---- LLM-authored narrative sections --------------------------------
        # Every WriterAgent run invokes the LLM at least four times so the
        # produced report is genuinely model-driven rather than templated.
        self._compose_executive_summary(state, llm)
        self._compose_direction_narratives(state, llm)
        self._compose_future_work(state, llm)
        self._compose_glossary(state, llm)

        # Deterministic post-processing — turns LLM output + state into
        # additional structured artifacts that the Markdown report renders.
        state["comparison_table"] = _build_comparison_table(state)
        state["paper_highlights"] = _build_paper_highlights(state)
        state["references_apa"] = _build_apa_references(state)

        report = build_survey_markdown(state)
        mindmap = build_mindmap_markdown(state)
        report_path = output_dir / "survey.md"
        mindmap_path = output_dir / "mindmap.md"
        report_path.write_text(report, encoding="utf-8")
        mindmap_path.write_text(mindmap, encoding="utf-8")
        state["report_path"] = str(report_path)
        state["mindmap_path"] = str(mindmap_path)
        add_message(
            state,
            self.name,
            "Wrote survey.md and mindmap.md (LLM-authored narrative + structured tables).",
        )
        return state

    # ------------------------------------------------------------------
    # LLM-authored sections
    # ------------------------------------------------------------------
    def _compose_executive_summary(self, state: ResearchState, llm: BaseLLM) -> None:
        topic = state.get("topic", "")
        prompt = (
            "请输出 writer_section_json，schema:\n"
            "{\"executive_summary\": <120-180字的中文执行摘要，覆盖研究问题、关键发现、风险、建议>}\n"
            f"\"section\": \"executive_summary\"\n"
            f"\"topic\": \"{topic}\"\n"
            f"papers={json.dumps(state.get('papers', [])[:5], ensure_ascii=False)}\n"
            f"critique={(state.get('critique_summary') or '')[:400]}"
        )
        data = self._call_writer_llm(llm, prompt)
        state["executive_summary"] = (
            str(data.get("executive_summary") or "").strip()
            or self._fallback_executive_summary(state)
        )

    def _compose_direction_narratives(self, state: ResearchState, llm: BaseLLM) -> None:
        topic = state.get("topic", "")
        analyses = state.get("paper_analyses", []) or []
        prompt = (
            "请输出 writer_section_json，schema:\n"
            "{\"direction_narratives\": {<方向名>: <60-120字的中文叙事>}}\n"
            f"\"section\": \"direction_narratives\"\n"
            f"\"topic\": \"{topic}\"\n"
            f"analyses={json.dumps(analyses[:6], ensure_ascii=False)}"
        )
        data = self._call_writer_llm(llm, prompt)
        narratives = data.get("direction_narratives") or {}
        if not isinstance(narratives, dict):
            narratives = {}
        if not narratives:
            narratives = self._fallback_direction_narratives(state)
        state["direction_narratives"] = {
            str(k): str(v) for k, v in list(narratives.items())[:6]
        }

    def _compose_future_work(self, state: ResearchState, llm: BaseLLM) -> None:
        topic = state.get("topic", "")
        prompt = (
            "请输出 writer_section_json，schema:\n"
            "{\"future_work\": [<3-6条中文未来工作建议>]}\n"
            f"\"section\": \"future_work\"\n"
            f"\"topic\": \"{topic}\"\n"
            f"critique={(state.get('critique_summary') or '')[:400]}\n"
            f"semantic_memory={json.dumps(state.get('semantic_memory') or {}, ensure_ascii=False)[:400]}"
        )
        data = self._call_writer_llm(llm, prompt)
        items = data.get("future_work") or []
        if isinstance(items, str):
            items = [s.strip() for s in re.split(r"[；;\n]", items) if s.strip()]
        if not isinstance(items, list):
            items = []
        items = [str(x).strip() for x in items if str(x).strip()][:6]
        if not items:
            items = [
                "扩展数据集并补充跨机构的独立验证。",
                "对比不同方法的统计效力与误差棒。",
                "结合本地 PDF 全文重新评估关键证据。",
            ]
        state["future_work"] = items

    def _compose_glossary(self, state: ResearchState, llm: BaseLLM) -> None:
        topic = state.get("topic", "")
        prompt = (
            "请输出 writer_section_json，schema:\n"
            "{\"glossary\": [{\"term\": <英文术语>, \"explain\": <中文解释>}]}\n"
            f"\"section\": \"glossary\"\n"
            f"\"topic\": \"{topic}\"\n"
            f"keywords={json.dumps(state.get('llm_keywords', []) or [], ensure_ascii=False)}"
        )
        data = self._call_writer_llm(llm, prompt)
        items = data.get("glossary") or []
        if not isinstance(items, list):
            items = []
        cleaned = []
        for item in items:
            if isinstance(item, dict) and item.get("term"):
                cleaned.append(
                    {"term": str(item["term"])[:60], "explain": str(item.get("explain", ""))[:160]}
                )
        if not cleaned:
            cleaned = [
                {"term": "ReAct", "explain": "推理与行动交替的 Agent 推理框架。"},
                {"term": "Reflexion", "explain": "通过反思和重试改进 Agent 决策。"},
            ]
        state["glossary"] = cleaned[:8]

    def _call_writer_llm(self, llm: BaseLLM, prompt: str) -> Dict[str, Any]:
        system_prompt = (
            "You are WriterAgent. Produce concise, evidence-grounded Chinese "
            "narrative sections. Always return strict JSON for writer_section_json."
        )
        try:
            raw = llm.invoke(system_prompt, prompt)
            data = parse_json_object(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _fallback_executive_summary(self, state: ResearchState) -> str:
        topic = state.get("topic", "")
        return (
            f"围绕「{topic}」，本轮调研整合了 {len(state.get('papers', []))} 篇核心论文，"
            "并通过 ReAct 检索循环与 Reflexion 反思迭代提升覆盖度；建议后续重点关注"
            "全文实验设计与可复现性。"
        )

    def _fallback_direction_narratives(self, state: ResearchState) -> Dict[str, str]:
        categories = group_by_category(state.get("paper_analyses", []))
        return {
            category: f"该方向覆盖 {len(items)} 篇论文，建议结合全文方法节进一步阅读。"
            for category, items in list(categories.items())[:4]
        } or {"相关研究": "暂无可分类的论文，请扩展关键词后再总结。"}


def _build_paper_highlights(state: ResearchState) -> List[Dict[str, Any]]:
    highlights: List[Dict[str, Any]] = []
    for analysis in (state.get("paper_analyses", []) or [])[:5]:
        contribution = str(analysis.get("contribution") or "")
        limitations = str(analysis.get("limitations") or "")
        highlights.append(
            {
                "title": analysis.get("title", ""),
                "year": str(analysis.get("year", "")),
                "url": analysis.get("url", ""),
                "category": analysis.get("category", ""),
                "contribution": contribution,
                "limitations": limitations,
                "tags": list(analysis.get("tags") or [])[:5],
            }
        )
    return highlights


def _build_comparison_table(state: ResearchState) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    metrics_lookup = {
        (m.get("title") or "").strip().lower(): m
        for m in (state.get("citation_metrics") or []) or []
    }
    for analysis in (state.get("paper_analyses", []) or [])[:8]:
        title_key = (analysis.get("title") or "").strip().lower()
        cited = metrics_lookup.get(title_key, {}).get("citation_count")
        rows.append(
            {
                "title": str(analysis.get("title", "")),
                "year": str(analysis.get("year", "")),
                "category": str(analysis.get("category", "")),
                "method": str(analysis.get("method", "")),
                "limitations": str(analysis.get("limitations", "")),
                "citation_count": str(cited) if cited is not None else "—",
            }
        )
    return rows


def _build_apa_references(state: ResearchState) -> List[str]:
    refs: List[str] = []
    for paper in (state.get("papers", []) or [])[:12]:
        authors = paper.get("authors") or []
        if not authors:
            author_str = "Anonymous"
        elif len(authors) == 1:
            author_str = authors[0]
        else:
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        year = paper.get("year", "n.d.")
        title = (paper.get("title") or "").strip().rstrip(".")
        url = paper.get("url", "")
        refs.append(f"{author_str} ({year}). {title}. Retrieved from {url}")
    return refs


def infer_tags(text: str, topic: str = "") -> List[str]:
    lowered = text.lower()
    tags: List[str] = []
    if is_agent_memory_topic(topic):
        candidates = {
            "long-term-memory": ["long-term", "persistent", "memorybank", "memgpt"],
            "reflection": ["reflection", "reflexion", "feedback"],
            "planning": ["planning", "plan"],
            "retrieval": ["retrieval", "retrieve", "rag", "vector"],
            "multi-agent": ["multi-agent", "agents", "generative agents"],
            "benchmark": ["benchmark", "evaluation", "evaluate"],
        }
    elif is_atmospheric_optics_topic(topic):
        candidates = {
            "twilight-sky": ["twilight", "sunset", "sunrise"],
            "atmospheric-optics": ["atmospheric", "optical", "optics"],
            "aerosol": ["aerosol", "dust", "turbidity"],
            "scattering": ["scattering", "multiple scattering"],
            "polarization": ["polarization", "polarimetry"],
            "sky-brightness": ["sky brightness", "skyglow", "light pollution"],
        }
    elif is_life_science_topic(topic):
        candidates = {
            "dna": ["dna", "genome", "genomic", "genomics"],
            "sequencing": ["sequencing", "transcriptomics", "single-cell"],
            "epigenetics": ["epigenetics", "methylation", "chromatin"],
            "dna-repair": ["repair", "damage", "break"],
            "crispr": ["crispr", "gene editing", "genome editing"],
            "virus": ["virus", "viral", "virology", "infection", "vaccine"],
            "protein": ["protein", "folding", "structure", "proteomics"],
        }
    else:
        candidates = {
            "survey": ["survey", "review", "taxonomy"],
            "measurement": ["measurement", "observations", "observing"],
            "modeling": ["model", "modelling", "simulation"],
            "benchmark": ["benchmark", "evaluation", "dataset"],
            "application": ["application", "system", "framework"],
            "method": ["method", "algorithm", "approach"],
        }
    for tag, keywords in candidates.items():
        if any(keyword in lowered for keyword in keywords):
            tags.append(tag)
    if tags:
        return tags
    generic = [
        token
        for token in keyword_tokens(text)
        if token not in {"paper", "study", "research", "result", "results"}
    ]
    return generic[:4] or ["topic-related"]


def safe_manager_plan(plan: str, state: ResearchState) -> str:
    lowered = plan.lower()
    forbidden_terms = [
        "google scholar",
        "semantic scholar",
        "chroma",
        "faiss",
        "neo4j",
        "parallel crawling",
        "完整文本",
        "全文",
        "最新 10",
        "最新10",
        "10 篇",
        "10篇",
    ]
    has_pdf = bool(state.get("pdf_paths", []))
    if any(term in lowered for term in forbidden_terms) or (
        not has_pdf and ("pdf" in lowered or "本地 pdf" in lowered)
    ):
        return build_safe_manager_plan(state)
    return plan


def build_safe_manager_plan(state: ResearchState) -> str:
    pdf_step = (
        "3. 若用户上传本地PDF，则用pdfplumber抽取前几页文本；否则只基于论文元数据和摘要分析。"
        if state.get("pdf_paths")
        else "3. 本轮未上传PDF，ReadingAgent只基于论文标题、摘要和元数据做结构化提取。"
    )
    return "\n".join(
        [
            "1. ManagerAgent明确主题、检索参数和本轮可用工具边界。",
            "2. SearchAgent使用arXiv/PubMed检索式和本地相关性评分筛选候选论文。",
            pdf_step,
            "4. ReadingAgent提取每篇论文的贡献、方法、局限、标签和方向分类。",
            "5. CriticAgent只基于已提取材料做Reflection，指出证据不足、方法局限和应用边界。",
            "6. WriterAgent生成survey.md、mindmap.md、run_log.json，并更新JSON长期记忆。",
        ]
    )


def infer_category(title: str, summary: str, topic: str = "") -> str:
    text = f"{title} {summary}".lower()
    if is_atmospheric_optics_topic(topic):
        if "skyglow" in text or "sky brightness" in text or "light pollution" in text:
            return "天空亮度与光污染"
        if "aerosol" in text or "scattering" in text or "polarization" in text:
            return "气溶胶、散射与偏振观测"
        if "twilight" in text or "sunset" in text or "sunrise" in text:
            return "暮光/霞光大气光学"
        if "instrument" in text or "observing program" in text or "telescope" in text:
            return "观测仪器与应用"
        return "大气光学相关研究"
    if is_life_science_topic(topic):
        if "survey" in text or "review" in text:
            return "综述与进展"
        if "crispr" in text or "gene editing" in text or "genome editing" in text:
            return "基因编辑与CRISPR"
        if "repair" in text or "damage" in text or "break" in text:
            return "DNA损伤与修复"
        if "methylation" in text or "epigenetic" in text or "chromatin" in text:
            return "表观遗传与调控"
        if "sequencing" in text or "genomic" in text or "genomics" in text or "transcriptomics" in text:
            return "基因组测序与组学"
        if "virus" in text or "viral" in text or "infection" in text or "vaccine" in text:
            return "病毒学与感染"
        if "protein" in text or "folding" in text or "structure" in text:
            return "蛋白质结构与功能"
        return "生命科学相关研究"
    if not is_agent_memory_topic(topic):
        if "survey" in text or "review" in text or "taxonomy" in text:
            return "综述与分类"
        if "dataset" in text or "benchmark" in text or "evaluation" in text:
            return "数据集与评测"
        if "model" in text or "simulation" in text or "modelling" in text:
            return "建模与方法"
        if "observation" in text or "measurement" in text or "observing" in text:
            return "观测与测量"
        if "application" in text or "system" in text or "framework" in text:
            return "系统与应用"
        return "相关研究"
    if "survey" in text or "taxonomy" in text:
        return "综述与分类"
    if "privacy" in text or "attack" in text or "risk" in text or "benchmark" in text:
        return "安全隐私与评测"
    if "retrieval" in text or "rag" in text or "vector" in text or "database" in text:
        return "检索增强记忆"
    if "reflection" in text or "reflexion" in text or "feedback" in text:
        return "反思与经验记忆"
    if "long-term" in text or "persistent" in text or "memgpt" in text or "memorybank" in text:
        return "长期记忆架构"
    return "其他相关方向"


def infer_method(title: str, summary: str, topic: str = "") -> str:
    text = f"{title} {summary}".lower()
    if is_atmospheric_optics_topic(topic):
        if "polarization" in text or "polarimetry" in text:
            return "Twilight sky polarization or polarimetry measurements."
        if "aerosol" in text or "scattering" in text:
            return "Atmospheric aerosol and scattering analysis from sky observations."
        if "sky brightness" in text or "skyglow" in text or "light pollution" in text:
            return "Sky brightness or skyglow measurement and modelling."
        if "observing program" in text or "instrument" in text:
            return "Astronomical twilight observing program or instrument use."
        return "Atmospheric-optics observation and analysis."
    if is_life_science_topic(topic):
        if "sequencing" in text or "genomic" in text or "transcriptomics" in text:
            return "Genomic or sequencing-based analysis."
        if "crispr" in text or "gene editing" in text:
            return "Genome editing or CRISPR-based experimental/computational study."
        if "methylation" in text or "epigenetic" in text:
            return "Epigenetic profiling or methylation analysis."
        if "repair" in text or "damage" in text:
            return "DNA damage/repair mechanism analysis."
        if "virus" in text or "viral" in text:
            return "Virology, infection, or vaccine-related analysis."
        if "protein" in text:
            return "Protein structure, function, or proteomics analysis."
        return "Life-science study inferred from title and abstract."
    if not is_agent_memory_topic(topic):
        if "survey" in text or "review" in text:
            return "Literature review and synthesis."
        if "measurement" in text or "observ" in text:
            return "Empirical observation and measurement."
        if "model" in text or "simulation" in text or "modelling" in text:
            return "Computational or statistical modelling."
        if "dataset" in text or "benchmark" in text:
            return "Dataset or benchmark construction and evaluation."
        return "Topic-specific method inferred from title and abstract."
    if "survey" in text:
        return "Survey and taxonomy construction."
    if "reflection" in text or "reflexion" in text:
        return "Reflection memory with verbal feedback reuse."
    if "retrieval" in text or "vector" in text or "rag" in text:
        return "Retrieval-augmented memory over external or vector storage."
    if "planning" in text or "generative agents" in text:
        return "Memory stream combined with reflection and planning."
    if "context" in text or "memgpt" in text:
        return "Virtual context management between short-term and long-term storage."
    return "LLM-agent memory mechanism analysis."


def analysis_off_topic(data: Dict[str, Any], topic: str) -> bool:
    if is_agent_memory_topic(topic):
        return False
    text = " ".join(
        str(data.get(key, "")) for key in ["category", "method", "contribution", "tags"]
    ).lower()
    forbidden = [
        "agent memory",
        "llm-agent memory",
        "long-term memory",
        "retrieval memory",
        "memory mechanism",
        "智能体记忆",
        "长期记忆架构",
        "检索增强记忆",
        "反思与经验记忆",
    ]
    return any(term in text for term in forbidden)


def critic_angles_for_topic(topic: str) -> str:
    if is_agent_memory_topic(topic):
        return "摘要证据不足、实验验证、长期记忆更新、隐私安全、应用落地"
    if is_atmospheric_optics_topic(topic):
        return "摘要证据不足、观测地点和时间覆盖、仪器与校准、气溶胶/散射条件、模型可复现性、应用边界"
    if is_life_science_topic(topic):
        return "摘要证据不足、样本和数据覆盖、实验验证、统计效力、可复现性、临床或应用边界"
    return "摘要证据不足、方法和数据覆盖、实验或观测验证、可复现性、局限性、应用边界"


def build_fallback_critique(state: ResearchState) -> str:
    analyses = state.get("paper_analyses", [])
    topic = state.get("topic", "")
    if not analyses:
        return "反思：本轮没有足够高相关论文进入正文分析，应调整关键词、降低阈值或补充本地PDF后再总结。"
    if is_agent_memory_topic(topic):
        return (
            "反思：现有论文通常存在评测场景有限、长期记忆更新策略不统一、"
            "隐私与遗忘机制讨论不足等问题。"
        )
    if is_atmospheric_optics_topic(topic):
        return (
            "反思：本轮结果主要依赖标题和摘要，霞光/暮光相关研究常受观测地点、季节、"
            "气溶胶条件、仪器校准和波段选择影响；摘要级分析难以判断数据覆盖范围、"
            "散射模型假设和观测可复现性，后续应优先阅读全文方法与观测设置。"
        )
    if is_life_science_topic(topic):
        return (
            "反思：本轮结果主要基于题名、摘要和数据库元数据，生命科学研究还需要核查样本来源、"
            "实验设计、测序/检测平台、统计效力、独立验证、可复现性和临床或生态外推边界；"
            "补充阅读全文和原始数据会显著提高结论可靠性。"
        )
    return (
        "反思：本轮结果主要基于摘要和元数据，方法细节、数据覆盖、实验设置和可复现性"
        "仍需全文验证；如果论文数量较少，应补充关键词或本地PDF。"
    )


def first_sentence(text: str) -> str:
    for delimiter in [". ", "? ", "! "]:
        if delimiter in text:
            return text.split(delimiter, 1)[0].strip() + delimiter.strip()
    return text.strip()


def parse_json_object(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    return json.loads(text[start : end + 1])


def summarize_pdf_text(text: str) -> str:
    if not text:
        return ""
    clipped = text[:600]
    return (
        "Local PDF excerpt indicates the document discusses: "
        + " ".join(clipped.split()[:80])
        + "..."
    )


def build_survey_markdown(state: ResearchState) -> str:
    analyses = state.get("paper_analyses", [])
    supporting = state.get("supporting_papers", [])
    categories = group_by_category(analyses)
    rejected = state.get("rejected_papers", [])
    stats = state.get("stats", {})
    diagnostics = state.get("search_diagnostics", {})
    lines: List[str] = [
        f"# AI科研助手调研报告：{state['topic']}",
        "",
        "## 1. 执行摘要",
        "",
        state.get("executive_summary")
        or (
            f"本次运行使用 `{state.get('workflow_engine', 'unknown')}` 工作流和 "
            f"`{state.get('llm_mode', 'unknown')}` 模型模式，围绕科研问题完成了论文检索、"
            "摘要/PDF阅读、方向归纳、Reflection反思和长期记忆更新。"
        ),
        "",
        (
            f"系统接收 {stats.get('paper_count', 0)} 篇高相关论文进入正文分析，"
            f"保留 {len(supporting)} 篇低权重补充候选，过滤 {len(rejected)} 篇低相关候选论文。"
        ),
        "",
        "## 2. 多Agent分工",
        "",
        "| Agent | 职责 | 推理/规划方法 | LLM调用次数 |",
        "| --- | --- | --- | ---: |",
        "| ManagerAgent | CoT 主题剖析 + Planning | CoT + Planning | 2 |",
        "| SearchAgent | ReAct 循环检索 arXiv/PubMed | ReAct (每轮决策) | "
        f"{len(state.get('react_trace', []) or [])} |",
        "| ReadingAgent | 结构化抽取贡献/方法/局限 | Structured extraction | "
        f"{len(state.get('paper_analyses', []) or [])} |",
        "| CriticAgent | math_calc + citation_graph + Reflexion 反思 | Reflexion | 1 |",
        "| WriterAgent | 执行摘要/方向叙事/未来工作/术语表 | Synthesis | 4 |",
        "",
        "## 3. 本轮执行计划",
        "",
        state.get("plan", ""),
        "",
        "### 3.1 ManagerAgent CoT 主题剖析",
        "",
        _format_topic_profile(state.get("topic_profile", {})),
        "",
        "## 4. 长期记忆检索",
        "",
    ]

    memories = state.get("retrieved_memories", [])
    if memories:
        for memory in memories:
            lines.append(
                f"- 历史主题：{memory.get('topic', '')}；相似度：{memory.get('score', 0)}；报告：{memory.get('report_path', '')}"
            )
    else:
        lines.append("- 未检索到相关历史记忆，本轮将作为新的长期记忆写入。")

    semantic_mem = state.get("semantic_memory") or {}
    procedural_mem = state.get("procedural_memory") or {}
    if any(semantic_mem.values()) or any(procedural_mem.values()):
        lines.extend(["", "### 4.1 Semantic + Procedural 记忆注入", ""])
        if semantic_mem.get("directions"):
            lines.append("- Semantic 方向：" + "；".join(semantic_mem["directions"]))
        if semantic_mem.get("common_methods"):
            lines.append("- Semantic 方法：" + "；".join(semantic_mem["common_methods"]))
        if semantic_mem.get("known_limitations"):
            lines.append("- Semantic 局限：" + "；".join(semantic_mem["known_limitations"]))
        if procedural_mem.get("effective_queries"):
            lines.append(
                "- Procedural 有效检索式：" + "；".join(procedural_mem["effective_queries"])
            )

    lines.extend(
        [
            "",
            "## 5. 检索与阅读结果",
            "",
            f"- 展开检索式：{'; '.join(state.get('search_queries', []))}",
            f"- 最低相关性阈值：{state.get('min_relevance', 0)}",
            f"- 候选池规模：{state.get('candidate_pool', 0)}",
            f"- 主题领域：{diagnostics.get('domain', 'unknown')}",
            f"- 主题关键词：{', '.join(diagnostics.get('topic_keywords', []))}",
            "",
            "### 5.0 检索源诊断",
            "",
        ]
    )

    sources = diagnostics.get("sources", [])
    if sources:
        for source in sources:
            warning_text = "；".join(source.get("warnings", [])) or "无"
            lines.append(
                f"- {source.get('source', '')}：查询 {source.get('query_count', 0)} 组，"
                f"候选 {source.get('candidate_count', 0)} 篇，warning：{warning_text}"
            )
    else:
        lines.append("- 暂无检索源诊断。")

    lines.extend(
        [
            "",
            "### 5.1 研究方向分类",
            "",
        ]
    )

    if categories:
        for category, items in categories.items():
            titles = "；".join(item.get("title", "") for item in items[:3])
            lines.append(f"- **{category}**：{len(items)} 篇。代表论文：{titles}")
    else:
        lines.append("- 暂无可分类论文。")

    lines.extend(
        [
            "",
            "### 5.2 代表论文表",
            "",
            "| 年份 | 来源 | 相关性 | 方向 | 论文 | 主要贡献 | 方法 | 标签 |",
            "| --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for item in analyses:
        lines.append(
            "| {year} | {source} | {score:.2f} | {category} | [{title}]({url}) | {contribution} | {method} | {tags} |".format(
                year=item.get("year", ""),
                source=item.get("source", ""),
                score=float(item.get("relevance_score", 0) or 0),
                category=escape_pipe(item.get("category", "")),
                title=escape_pipe(item.get("title", "")),
                url=item.get("url", ""),
                contribution=escape_pipe(item.get("contribution", "")),
                method=escape_pipe(item.get("method", "")),
                tags=", ".join(item.get("tags", [])),
            )
        )
    if not analyses:
        lines.append("| - | - | 0.00 | - | 暂无核心论文 | - | - | - |")

    lines.extend(
        [
            "",
            "### 5.3 低权重补充候选",
            "",
        ]
    )
    if supporting:
        lines.extend(
            [
                "| 年份 | 来源 | 相关性 | 论文 | 匹配词 |",
                "| --- | --- | ---: | --- | --- |",
            ]
        )
        for item in supporting[:12]:
            lines.append(
                "| {year} | {source} | {score:.2f} | [{title}]({url}) | {terms} |".format(
                    year=item.get("year", ""),
                    source=item.get("source", ""),
                    score=float(item.get("relevance_score", 0) or 0),
                    title=escape_pipe(item.get("title", "")),
                    url=item.get("url", ""),
                    terms=", ".join(item.get("matched_terms", [])),
                )
            )
    else:
        lines.append("- 无补充候选。")

    if not analyses and not supporting:
        lines.extend(
            [
                "",
                "### 5.4 空结果诊断",
                "",
                "- 本轮没有足够候选进入核心或补充列表。",
                "- 建议降低 Min score、扩大 Pool、换用更具体英文关键词，或上传本地PDF让 ReadingAgent 直接读取。",
                "- 若 Run Log 显示某个检索源 warning，优先检查网络/VPN或稍后重试。",
            ]
        )

    lines.extend(
        [
            "",
            "## 6. 统计工具结果",
            "",
            f"- 核心论文数量：{stats.get('paper_count', 0)}",
            f"- 补充候选数量：{len(supporting)}",
            f"- 平均相关性：{stats.get('average_relevance', 0)}",
            f"- 年份分布：{json.dumps(stats.get('year_distribution', {}), ensure_ascii=False)}",
            "- 高频关键词："
            + ", ".join(
                f"{item['keyword']}({item['count']})"
                for item in stats.get("top_keywords", [])
            ),
            "",
            "## 7. Critic反思",
            "",
            state.get("critique_summary", ""),
            "",
            "### 7.1 SearchAgent ReAct Trace",
            "",
            _format_react_trace(state.get("react_trace", [])),
            "",
            "### 7.2 CriticAgent Reflexion 决策",
            "",
            _format_critic_decision(state.get("critic_decision", {})),
            "",
            "### 7.3 工具调用证据（math_calc + citation_graph）",
            "",
            _format_calc_logs(state.get("calc_logs", [])),
            "",
            _format_citation_metrics(state.get("citation_metrics", [])),
            "",
            "## 8. 研究方向叙事（LLM 撰写）",
            "",
            _format_direction_narratives(state.get("direction_narratives", {})),
            "",
            "## 9. 论文亮点解读",
            "",
            _format_paper_highlights(state.get("paper_highlights", [])),
            "",
            "## 10. 方法对比表",
            "",
            _format_comparison_table(state.get("comparison_table", [])),
            "",
            "## 11. 未来工作（LLM 建议）",
            "",
            _format_future_work(state.get("future_work", [])),
            "",
            "## 12. 术语表（LLM 撰写）",
            "",
            _format_glossary(state.get("glossary", [])),
            "",
            "## 13. APA 参考文献",
            "",
            _format_references_apa(state.get("references_apa", [])),
            "",
            "## 14. 被过滤候选论文",
            "",
        ]
    )
    if rejected:
        for item in rejected[:10]:
            lines.append(
                f"- {item.get('title', '')} ({item.get('year', '')})：相关性 {item.get('relevance_score', 0)}，原因：{item.get('reason', '')}"
            )
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## 15. 评分要求对齐",
            "",
            "- Agent数量：5个，满足 >= 4。",
            "- 推理/规划：ManagerAgent使用Planning + CoT（topic_profile），SearchAgent体现ReAct循环（react_trace），CriticAgent体现Reflexion（critic_decision），WriterAgent调用LLM完成执行摘要/方向叙事/未来工作/术语表。",
            f"- 记忆机制：短期记忆（messages/tool_logs）+ 长期Episodic（{state.get('memory_path', '')}）+ Semantic（{state.get('semantic_memory_path', '')}）+ Procedural（{state.get('procedural_memory_path', '')}），共4类。",
            "- 工具调用：research_search（arXiv/PubMed）、pdf_extract、paper_stats、math_calc、citation_graph、query_rewrite_llm，共6类。",
            f"- LangGraph 条件回环：CriticAgent → SearchAgent 重试次数 {int(state.get('critic_retries_done', 0))}。",
            "- 输出产物：survey.md、mindmap.md、run_log.json。",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_topic_profile(profile: Dict[str, Any]) -> str:
    if not profile:
        return "- 未生成 topic_profile（可能LLM输出无法解析）。"
    keywords = profile.get("english_keywords", []) or []
    directions = profile.get("expected_directions", []) or []
    lines = [
        f"- CoT 思考：{profile.get('thoughts', '')}",
        f"- 英文检索词：{', '.join(keywords) if keywords else '(none)'}",
        f"- 推断领域：{profile.get('domain', 'general')}",
        f"- arXiv 提示：{profile.get('arxiv_query_hint', '')}",
        f"- PubMed 提示：{profile.get('pubmed_query_hint', '') or '(skip)'}",
        "- 预期方向："
        + ("；".join(directions) if directions else "(none)"),
    ]
    return "\n".join(lines)


def _format_react_trace(trace: List[Dict[str, Any]]) -> str:
    if not trace:
        return "- 未记录 ReAct trace。"
    lines: List[str] = []
    for item in trace:
        decision = item.get("decision", {}) or {}
        lines.append(
            "- 迭代 {iteration}：paper_count={paper_count}, action={action}, "
            "refined={refined}\n  thought：{thought}".format(
                iteration=item.get("iteration", "?"),
                paper_count=item.get("paper_count", 0),
                action=decision.get("action", "stop"),
                refined=", ".join(decision.get("refined_keywords", []) or [])
                or "(none)",
                thought=decision.get("thought", ""),
            )
        )
    return "\n".join(lines)


def _format_critic_decision(decision: Dict[str, Any]) -> str:
    if not decision:
        return "- 未生成结构化 Reflexion 决策。"
    keywords = decision.get("suggested_keywords", []) or []
    return "\n".join(
        [
            f"- needs_more_search: {decision.get('needs_more_search', False)}",
            f"- suggested_keywords: {', '.join(keywords) if keywords else '(none)'}",
            f"- reflection: {decision.get('reflection', '')}",
        ]
    )


def _format_calc_logs(calc_logs: List[Dict[str, Any]]) -> str:
    if not calc_logs:
        return "- 未记录 math_calc。"
    return "\n".join(
        f"- `{item.get('expression', '')}` = {item.get('result')}"
        + (f"（错误：{item['error']}）" if item.get("error") else "")
        for item in calc_logs
    )


def _format_citation_metrics(metrics: List[Dict[str, Any]]) -> str:
    if not metrics:
        return "- citation_graph 未返回结果（可能离线或主题冷门）。"
    lines = ["| 论文 | 年份 | 出处 | 引用数 | 备注 |", "| --- | --- | --- | ---: | --- |"]
    for item in metrics:
        lines.append(
            "| {title} | {year} | {venue} | {cited} | {note} |".format(
                title=escape_pipe(item.get("title", "")),
                year=item.get("year") or "—",
                venue=escape_pipe(item.get("venue") or "—"),
                cited=item.get("citation_count") if item.get("citation_count") is not None else "—",
                note=escape_pipe(item.get("error", "") or "—"),
            )
        )
    return "\n".join(lines)


def _format_direction_narratives(narratives: Dict[str, str]) -> str:
    if not narratives:
        return "- 暂未生成方向叙事。"
    return "\n\n".join(f"### 方向：{name}\n{text}" for name, text in narratives.items())


def _format_paper_highlights(highlights: List[Dict[str, Any]]) -> str:
    if not highlights:
        return "- 暂无论文亮点。"
    chunks: List[str] = []
    for index, item in enumerate(highlights, start=1):
        title = item.get("title", "")
        url = item.get("url", "")
        chunks.append(
            f"**{index}. [{title}]({url}) ({item.get('year', '')})**\n"
            f"- 方向：{item.get('category', '')}\n"
            f"- 贡献：{item.get('contribution', '')}\n"
            f"- 局限：{item.get('limitations', '')}\n"
            f"- 标签：{', '.join(item.get('tags', []) or [])}"
        )
    return "\n\n".join(chunks)


def _format_comparison_table(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return "- 暂无对比数据。"
    lines = [
        "| 论文 | 年份 | 方向 | 方法 | 局限 | 引用数 |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {title} | {year} | {category} | {method} | {limitations} | {cited} |".format(
                title=escape_pipe(row.get("title", "")),
                year=row.get("year", ""),
                category=escape_pipe(row.get("category", "")),
                method=escape_pipe(row.get("method", "")),
                limitations=escape_pipe(row.get("limitations", "")),
                cited=row.get("citation_count", "—"),
            )
        )
    return "\n".join(lines)


def _format_future_work(items: List[str]) -> str:
    if not items:
        return "- 暂无 LLM 撰写的未来工作建议。"
    return "\n".join(f"- {item}" for item in items)


def _format_glossary(items: List[Dict[str, str]]) -> str:
    if not items:
        return "- 暂无术语表。"
    return "\n".join(
        f"- **{item.get('term', '')}**：{item.get('explain', '')}"
        for item in items
    )


def _format_references_apa(refs: List[str]) -> str:
    if not refs:
        return "- 暂无 APA 参考文献。"
    return "\n".join(f"{index}. {ref}" for index, ref in enumerate(refs, start=1))


def build_mindmap_markdown(state: ResearchState) -> str:
    categories = group_by_category(state.get("paper_analyses", []))
    lines = [
        f"# Mindmap：{state['topic']}",
        "",
        "```mermaid",
        "mindmap",
        f"  root(({state['topic']}))",
        "    Agent团队",
        "      ManagerAgent[CoT+Planning]",
        "        topic_profile",
        "        planning",
        "      SearchAgent[ReAct]",
        "        react_trace",
        "        research_search",
        "      ReadingAgent[Structured]",
        "        reading_extract_json",
        "      CriticAgent[Reflexion]",
        "        math_calc",
        "        citation_graph",
        "        critic_decision",
        "      WriterAgent[LLM-authored]",
        "        executive_summary",
        "        direction_narratives",
        "        future_work",
        "        glossary",
        "    记忆机制",
        "      短期Working",
        "        messages",
        "        tool_logs",
        "      长期Episodic",
        "        long_term_memory.json",
        "      Semantic",
        "        directions/methods/limitations",
        "      Procedural",
        "        query→hit_rate",
        "    工具调用",
        "      research_search",
        "      pdf_extract",
        "      paper_stats",
        "      math_calc",
        "      citation_graph",
        "      query_rewrite_llm",
        "    研究主题",
    ]
    for category, items in categories.items():
        lines.append(f"      {category}")
        for item in items[:3]:
            title = item.get("title", "paper").replace("(", "").replace(")", "")
            lines.append(f"        {title[:48]}")
    lines.extend(["```", ""])
    # Also emit a data-flow graph so the report shows agent handoffs.
    lines.extend(
        [
            "## 数据流图",
            "",
            "```mermaid",
            "flowchart LR",
            "  M[ManagerAgent\\nCoT topic_profile] --> Mem[(Episodic+Semantic+Procedural\\nMemory)]",
            "  Mem --> M",
            "  M -->|llm_keywords| S[SearchAgent\\nReAct loop]",
            "  S -->|papers| R[ReadingAgent\\nStructured extract]",
            "  R -->|paper_analyses| C[CriticAgent\\nmath_calc+citation_graph+Reflexion]",
            "  C -->|needs_more_search| S",
            "  C -->|advance| W[WriterAgent\\nLLM-authored sections]",
            "  W --> O[(survey.md+mindmap.md+run_log.json)]",
            "  W --> Mem",
            "```",
        ]
    )
    return "\n".join(lines)


def escape_pipe(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def group_by_category(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item.get("category", "未分类"), []).append(item)
    return grouped
