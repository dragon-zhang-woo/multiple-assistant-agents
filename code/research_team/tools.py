from __future__ import annotations

import re
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


def normalize_arxiv_query(topic: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", topic):
        lowered = topic.lower()
        if "agent" in lowered and "memory" in lowered:
            return "agent memory large language model"
        return "large language model agent"
    return topic.strip() or "agent memory"


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
        ),
    ]
    return examples[:max_results]


def arxiv_search(
    topic: str, max_results: int = 5, timeout: int = 25
) -> Tuple[List[Paper], List[str]]:
    warnings: List[str] = []
    query = normalize_arxiv_query(topic)
    params = {
        "search_query": "all:" + query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    try:
        response = requests.get(
            "https://export.arxiv.org/api/query", params=params, timeout=timeout
        )
        response.raise_for_status()
        papers = parse_arxiv_response(response.text)
        if papers:
            return papers[:max_results], warnings
        warnings.append("arXiv returned no entries; using fallback paper samples.")
    except Exception as exc:
        warnings.append(f"arXiv search failed ({exc}); using fallback paper samples.")
    return fallback_papers(topic, max_results), warnings


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
    }


def keyword_tokens(text: str) -> List[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)
        if token.lower() not in STOPWORDS
    ]
