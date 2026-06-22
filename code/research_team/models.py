from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, TypedDict


@dataclass
class Paper:
    title: str
    authors: List[str]
    year: str
    summary: str
    url: str
    pdf_url: str = ""
    source: str = "arxiv"
    importance: str = "core"
    domain: str = "general"
    relevance_score: float = 0.0
    matched_terms: List[str] | None = None
    topic_keywords: List[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data["matched_terms"] is None:
            data["matched_terms"] = []
        if data["topic_keywords"] is None:
            data["topic_keywords"] = []
        return data


@dataclass
class PaperAnalysis:
    title: str
    year: str
    url: str
    contribution: str
    method: str
    limitations: str
    tags: List[str]
    source: str = "arxiv"
    category: str = "未分类"
    relevance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchState(TypedDict, total=False):
    topic: str
    max_papers: int
    pdf_paths: List[str]
    output_dir: str
    memory_path: str
    messages: List[Dict[str, str]]
    tool_logs: List[Dict[str, Any]]
    warnings: List[str]
    retrieved_memories: List[Dict[str, Any]]
    papers: List[Dict[str, Any]]
    supporting_papers: List[Dict[str, Any]]
    rejected_papers: List[Dict[str, Any]]
    search_queries: List[str]
    search_diagnostics: Dict[str, Any]
    paper_analyses: List[Dict[str, Any]]
    pdf_notes: List[Dict[str, str]]
    stats: Dict[str, Any]
    plan: str
    topic_profile: Dict[str, Any]
    llm_keywords: List[str]
    react_trace: List[Dict[str, Any]]
    critic_decision: Dict[str, Any]
    critic_retries: int
    critic_retries_done: int
    critique_summary: str
    report_path: str
    mindmap_path: str
    run_log_path: str
    latest_dir: str
    workflow_engine: str
    llm_mode: str
    candidate_pool: int
    min_relevance: float
    sort_by: str
    run_name: str
    started_at: str
    completed_at: str
    semantic_memory: Dict[str, Any]
    procedural_memory: Dict[str, Any]
    semantic_memory_path: str
    procedural_memory_path: str
    executive_summary: str
    direction_narratives: Dict[str, str]
    paper_highlights: List[Dict[str, Any]]
    comparison_table: List[Dict[str, str]]
    future_work: List[str]
    glossary: List[Dict[str, str]]
    references_apa: List[str]
    citation_metrics: List[Dict[str, Any]]
    calc_logs: List[Dict[str, Any]]
    rewrite_history: List[Dict[str, Any]]
