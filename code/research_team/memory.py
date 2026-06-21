from __future__ import annotations

import json
import math
import re
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


class LongTermMemory:
    """A small JSON vector-style memory store using bag-of-words cosine scores."""

    def __init__(self, path: Path):
        self.path = path
        self.entries = self._load()

    def retrieve(
        self, query: str, top_k: int = 3, min_score: float = 0.12
    ) -> List[Dict[str, Any]]:
        query_vec = text_vector(expand_query_for_memory(query))
        query_domain = infer_domain(query)
        query_keywords = set(infer_keywords(query))
        scored: List[Dict[str, Any]] = []
        for entry in self.entries:
            entry_domain = entry.get("domain", "general")
            entry_keywords = set(entry.get("topic_keywords", []))
            if query_domain != "general" and entry_domain not in {query_domain, "general", ""}:
                continue
            if query_keywords and entry_keywords and not (query_keywords & entry_keywords):
                continue
            evidence_text = " ".join(
                [
                    " ".join(p.get("title", "") for p in entry.get("papers", [])),
                    " ".join(entry.get("tags", [])),
                    " ".join(entry.get("topic_keywords", [])),
                ]
            )
            if entry.get("papers") and cosine(query_vec, text_vector(evidence_text)) == 0:
                continue
            text = " ".join(
                [
                    entry.get("topic", ""),
                    evidence_text,
                ]
            )
            score = cosine(query_vec, text_vector(text))
            if score >= min_score:
                item = dict(entry)
                item["score"] = round(score, 4)
                scored.append(item)
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def add_run(
        self,
        topic: str,
        papers: Iterable[Dict[str, Any]],
        analyses: Iterable[Dict[str, Any]],
        report_path: str,
    ) -> None:
        paper_list = list(papers)
        analysis_list = list(analyses)
        tags = sorted({tag for item in analysis_list for tag in item.get("tags", [])})
        sources = sorted({paper.get("source", "") for paper in paper_list if paper.get("source")})
        fingerprint = run_fingerprint(topic, paper_list)
        entry = {
            "id": f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "fingerprint": fingerprint,
            "topic": topic,
            "domain": infer_domain(topic),
            "sources": sources,
            "topic_keywords": infer_keywords(topic),
            "papers": [
                {
                    "title": paper.get("title", ""),
                    "year": paper.get("year", ""),
                    "url": paper.get("url", ""),
                    "source": paper.get("source", ""),
                }
                for paper in paper_list
            ],
            "tags": tags,
            "report_path": report_path,
        }
        existing_index = next(
            (
                index
                for index, existing in enumerate(self.entries)
                if existing.get("fingerprint") == fingerprint
            ),
            None,
        )
        if existing_index is None:
            self.entries.append(entry)
        else:
            entry["id"] = self.entries[existing_index].get("id", entry["id"])
            self.entries[existing_index] = entry
        self._save()

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def text_vector(text: str) -> Counter:
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    for chinese_text in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.append(chinese_text)
        tokens.extend(
            chinese_text[index : index + 2]
            for index in range(max(len(chinese_text) - 1, 0))
        )
    return Counter(tokens)


def expand_query_for_memory(query: str) -> str:
    try:
        from research_team.tools import normalize_arxiv_query

        return f"{query} {normalize_arxiv_query(query)}"
    except Exception:
        return query


def infer_domain(query: str) -> str:
    try:
        from research_team.tools import infer_topic_domain

        return infer_topic_domain(query)
    except Exception:
        return "general"


def infer_keywords(query: str) -> List[str]:
    try:
        from research_team.tools import topic_keywords

        return topic_keywords(query)
    except Exception:
        return list(text_vector(query).keys())[:12]


def cosine(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def run_fingerprint(topic: str, papers: Iterable[Dict[str, Any]]) -> str:
    normalized_topic = " ".join(topic.lower().split())
    urls = sorted(paper.get("url", "") or paper.get("title", "") for paper in papers)
    raw = json.dumps([normalized_topic, urls], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
