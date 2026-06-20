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

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_vec = text_vector(query)
        scored: List[Dict[str, Any]] = []
        for entry in self.entries:
            text = " ".join(
                [
                    entry.get("topic", ""),
                    " ".join(p.get("title", "") for p in entry.get("papers", [])),
                    " ".join(entry.get("tags", [])),
                ]
            )
            score = cosine(query_vec, text_vector(text))
            if score > 0:
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
        fingerprint = run_fingerprint(topic, paper_list)
        entry = {
            "id": f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "fingerprint": fingerprint,
            "topic": topic,
            "papers": [
                {
                    "title": paper.get("title", ""),
                    "year": paper.get("year", ""),
                    "url": paper.get("url", ""),
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
    tokens = re.findall(r"[\u4e00-\u9fff]|[A-Za-z][A-Za-z\-]{2,}", text.lower())
    return Counter(tokens)


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
