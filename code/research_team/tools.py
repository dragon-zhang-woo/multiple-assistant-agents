from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import requests

from research_team.models import Paper


STOPWORDS = {
    "about",
    "after",
    "agent",
    "agents",
    "also",
    "based",
    "between",
    "from",
    "large",
    "language",
    "learning",
    "memory",
    "model",
    "models",
    "paper",
    "system",
    "systems",
    "that",
    "their",
    "these",
    "this",
    "using",
    "with",
}

POSITIVE_PATTERNS = {
    "agent memory": 5.0,
    "llm agent memory": 5.0,
    "long-term agent memory": 4.0,
    "memory-augmented agent": 4.0,
    "memory augmented agent": 4.0,
    "persistent memory": 2.5,
    "episodic memory": 2.0,
    "semantic memory": 2.0,
    "memory consolidation": 2.0,
    "memory retrieval": 2.0,
    "chat agents": 1.5,
    "generative agents": 1.5,
}

NEGATIVE_PATTERNS = {
    "proton": 5.0,
    "collision": 5.0,
    "boson": 5.0,
    "electroweak": 5.0,
    "diffusiongemma": 4.0,
    "diffusion": 3.0,
    "egocentric video": 4.0,
    "video question answering": 3.0,
    "wearable cameras": 3.0,
    "temporal reasoning": 2.0,
}


def normalize_arxiv_query(topic: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", topic):
        lowered = topic.lower()
        if "agent" in lowered and "memory" in lowered:
            return "agent memory large language model"
        return "large language model agent"
    return topic.strip() or "agent memory"


def build_arxiv_queries(topic: str) -> List[str]:
    normalized = normalize_arxiv_query(topic)
    lowered = normalized.lower()
    if "agent" in lowered and "memory" in lowered:
        return [
            'all:"agent memory"',
            '(ti:"agent memory" OR abs:"agent memory" OR ti:"memory augmented agent" OR abs:"memory augmented agent")',
            '(all:"LLM agent" AND all:"memory")',
            '(all:"long-term memory" AND all:"agent")',
        ]
    escaped = normalized.replace('"', "")
    return [f'all:"{escaped}"', f"all:{escaped}"]


def fallback_papers(topic: str, max_results: int) -> List[Paper]:
    examples = [
        Paper(
            title="A Survey on the Memory Mechanism of Large Language Model based Agents",
            authors=["Example Research Team"],
            year="2024",
            summary=(
                "This survey summarizes memory modules for LLM agents, including "
                "working memory, episodic memory, semantic memory, retrieval, and "
                "reflection-driven consolidation."
            ),
            url="https://arxiv.org/abs/2404.13501",
            pdf_url="https://arxiv.org/pdf/2404.13501",
            source="fallback",
            relevance_score=8.0,
            matched_terms=["survey", "agent memory", "reflection", "retrieval"],
        ),
        Paper(
            title="Generative Agents: Interactive Simulacra of Human Behavior",
            authors=["Joon Sung Park", "Joseph O'Brien", "Carrie Cai"],
            year="2023",
            summary=(
                "The paper introduces generative agents with memory streams, "
                "reflection, and planning to produce believable long-horizon behavior."
            ),
            url="https://arxiv.org/abs/2304.03442",
            pdf_url="https://arxiv.org/pdf/2304.03442",
            source="fallback",
            relevance_score=6.5,
            matched_terms=["generative agents", "reflection", "planning"],
        ),
        Paper(
            title="Reflexion: Language Agents with Verbal Reinforcement Learning",
            authors=["Noah Shinn", "Federico Cassano", "Ashwin Gopinath"],
            year="2023",
            summary=(
                "Reflexion lets language agents store verbal feedback from previous "
                "attempts and reuse it as memory for future decision making."
            ),
            url="https://arxiv.org/abs/2303.11366",
            pdf_url="https://arxiv.org/pdf/2303.11366",
            source="fallback",
            relevance_score=6.0,
            matched_terms=["reflexion", "feedback", "memory"],
        ),
        Paper(
            title="MemGPT: Towards LLMs as Operating Systems",
            authors=["Charles Packer", "Vivian Fang", "Shishir G. Patil"],
            year="2023",
            summary=(
                "MemGPT proposes virtual context management that moves information "
                "between limited context windows and longer-term storage."
            ),
            url="https://arxiv.org/abs/2310.08560",
            pdf_url="https://arxiv.org/pdf/2310.08560",
            source="fallback",
            relevance_score=6.0,
            matched_terms=["memgpt", "long-term memory", "context"],
        ),
        Paper(
            title="MemoryBank: Enhancing Large Language Models with Long-Term Memory",
            authors=["Example Authors"],
            year="2023",
            summary=(
                "MemoryBank explores persistent user-level memory, forgetting, and "
                "retrieval to improve personalized LLM interactions."
            ),
            url="https://arxiv.org/abs/2305.10250",
            pdf_url="https://arxiv.org/pdf/2305.10250",
            source="fallback",
            relevance_score=5.5,
            matched_terms=["memorybank", "long-term memory"],
        ),
    ]
    return examples[:max_results]


def arxiv_search(
    topic: str,
    max_results: int = 5,
    timeout: int = 25,
    candidate_pool: int = 25,
    min_relevance: float = 3.0,
    sort_by: str = "relevance",
) -> Tuple[List[Paper], List[str], List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    queries = build_arxiv_queries(topic)
    if candidate_pool <= 0:
        warnings.append("candidate_pool <= 0; using fallback paper samples without arXiv network access.")
        return fallback_papers(topic, max_results), warnings, [], queries
    all_candidates: Dict[str, Paper] = {}
    per_query = max(max_results, min(candidate_pool, 10))

    for index, query in enumerate(queries):
        params = {
            "search_query": query,
            "start": "0",
            "max_results": str(per_query),
            "sortBy": "relevance" if sort_by == "relevance" else "submittedDate",
            "sortOrder": "descending",
        }
        try:
            response = requests.get(
                "https://export.arxiv.org/api/query", params=params, timeout=timeout
            )
            response.raise_for_status()
            for paper in parse_arxiv_response(response.text):
                key = paper.url or paper.title.lower()
                existing = all_candidates.get(key)
                scored = score_paper_relevance(paper, topic)
                if existing is None or scored.relevance_score > existing.relevance_score:
                    all_candidates[key] = scored
        except Exception as exc:
            warnings.append(f"arXiv query failed for {query} ({exc}).")
        if index < len(queries) - 1:
            time.sleep(1)

    accepted, rejected = filter_relevant_papers(
        all_candidates.values(), max_results=max_results, min_relevance=min_relevance
    )
    if accepted:
        if len(accepted) < max_results:
            warnings.append(
                f"Only {len(accepted)} papers passed relevance filtering; requested {max_results}."
            )
        return accepted, warnings, rejected, queries

    warnings.append("No arXiv candidates passed relevance filtering; using fallback paper samples.")
    return fallback_papers(topic, max_results), warnings, rejected, queries


def parse_arxiv_response(xml_text: str) -> List[Paper]:
    root = ET.fromstring(xml_text)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    papers: List[Paper] = []
    for entry in root.findall("atom:entry", ns):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
        summary = clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year = published[:4] if published else "unknown"
        authors = [
            clean_text(author.findtext("atom:name", default="", namespaces=ns))
            for author in entry.findall("atom:author", ns)
        ]
        url = entry.findtext("atom:id", default="", namespaces=ns)
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href", "")
                break
        if title:
            papers.append(
                Paper(
                    title=title,
                    authors=[a for a in authors if a],
                    year=year,
                    summary=summary,
                    url=url,
                    pdf_url=pdf_url,
                )
            )
    return papers


def score_paper_relevance(paper: Paper, topic: str) -> Paper:
    title = paper.title.lower()
    summary = paper.summary.lower()
    combined = f"{title} {summary}"
    score = 0.0
    matched_terms: List[str] = []

    for phrase, weight in POSITIVE_PATTERNS.items():
        if phrase in title:
            score += weight * 1.4
            matched_terms.append(phrase)
        elif phrase in summary:
            score += weight
            matched_terms.append(phrase)

    if "agent" in combined and "memory" in combined:
        score += 2.5
        matched_terms.append("agent+memory")
    if ("llm" in combined or "large language model" in combined) and "memory" in combined:
        score += 1.5
        matched_terms.append("llm+memory")

    topic_tokens = {
        token
        for token in keyword_tokens(normalize_arxiv_query(topic))
        if token not in {"recent", "research", "direction", "directions"}
    }
    candidate_tokens = set(keyword_tokens(combined))
    overlap = sorted(topic_tokens & candidate_tokens)
    score += min(len(overlap), 5) * 0.6
    matched_terms.extend(overlap)

    for phrase, penalty in NEGATIVE_PATTERNS.items():
        if phrase in combined:
            score -= penalty

    if paper.year.isdigit():
        year = int(paper.year)
        if year >= 2023:
            score += 0.5
        elif year < 2020:
            score -= 0.5

    paper.relevance_score = round(score, 3)
    paper.matched_terms = sorted(set(matched_terms))
    return paper


def filter_relevant_papers(
    papers: Iterable[Paper], max_results: int, min_relevance: float
) -> Tuple[List[Paper], List[Dict[str, Any]]]:
    accepted: List[Paper] = []
    rejected: List[Dict[str, Any]] = []
    for paper in papers:
        if paper.relevance_score >= min_relevance:
            accepted.append(paper)
        else:
            rejected.append(
                {
                    "title": paper.title,
                    "year": paper.year,
                    "url": paper.url,
                    "relevance_score": paper.relevance_score,
                    "reason": "below min_relevance",
                }
            )
    accepted.sort(key=lambda item: (item.relevance_score, item.year), reverse=True)
    rejected.sort(key=lambda item: item["relevance_score"])
    return accepted[:max_results], rejected


def clean_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def extract_pdf_text(
    pdf_path: Path, max_pages: int = 3, max_chars: int = 6000
) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    if not pdf_path.exists():
        return "", [f"PDF not found: {pdf_path}"]

    try:
        import pdfplumber
    except Exception as exc:
        return "", [f"pdfplumber is not installed, cannot read {pdf_path}: {exc}"]

    chunks: List[str] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages[:max_pages]:
                chunks.append(page.extract_text() or "")
    except Exception as exc:
        return "", [f"Failed to read PDF {pdf_path}: {exc}"]

    text = clean_text("\n".join(chunks))[:max_chars]
    if not text:
        warnings.append(f"No extractable text found in PDF: {pdf_path}")
    return text, warnings


def paper_stats(papers: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    paper_list = list(papers)
    years = Counter(str(p.get("year", "unknown")) for p in paper_list)
    words: List[str] = []
    for paper in paper_list:
        words.extend(keyword_tokens(paper.get("title", "")))
        words.extend(keyword_tokens(paper.get("summary", "")))
    top_keywords = [
        {"keyword": word, "count": count}
        for word, count in Counter(words).most_common(12)
        if word not in STOPWORDS
    ]
    return {
        "paper_count": len(paper_list),
        "year_distribution": dict(sorted(years.items())),
        "top_keywords": top_keywords[:8],
        "average_relevance": round(
            sum(float(p.get("relevance_score", 0) or 0) for p in paper_list)
            / len(paper_list),
            3,
        )
        if paper_list
        else 0,
    }


def keyword_tokens(text: str) -> List[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)
        if token.lower() not in STOPWORDS
    ]
