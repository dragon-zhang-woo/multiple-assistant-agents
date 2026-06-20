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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    paper_analyses: List[Dict[str, Any]]
    pdf_notes: List[Dict[str, str]]
    stats: Dict[str, Any]
    plan: str
    critique_summary: str
    report_path: str
    mindmap_path: str
    run_log_path: str
    workflow_engine: str
    llm_mode: str
    started_at: str
    completed_at: str
