from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
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
    "recent",
    "research",
    "study",
    "studies",
    "direction",
    "directions",
}

SHORT_KEYWORDS = {
    "ai",
    "dna",
    "rna",
    "llm",
    "gpt",
}

CHINESE_INTENT_WORDS = [
    "有关",
    "关于",
    "最近",
    "近年来",
    "研究",
    "有哪些",
    "有什么",
    "具体",
    "方向",
    "论文",
    "调研",
    "报告",
    "？",
    "?",
]

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
    "chameleon": 4.0,
    "gravitational lensing": 4.0,
    "wave-optics": 3.0,
    "gamma-ray": 4.0,
    "particle": 2.0,
}

CHINESE_QUERY_TERMS = {
    "霞光": "twilight sky skyglow atmospheric optics sunset sunrise scattering aerosol polarization",
    "晚霞": "twilight sky skyglow atmospheric optics sunset scattering aerosol polarization",
    "朝霞": "twilight sky skyglow atmospheric optics sunrise scattering aerosol polarization",
    "余晖": "twilight sky skyglow atmospheric optics sunset scattering aerosol polarization",
    "大气光学": "atmospheric optics twilight skyglow scattering",
    "人工智能": "artificial intelligence machine learning deep learning",
    "机器学习": "machine learning",
    "深度学习": "deep learning neural networks",
    "大模型": "large language model",
    "语言模型": "language model",
    "智能体": "agent",
    "多智能体": "multi-agent agents",
    "记忆": "memory",
    "长期记忆": "long-term memory",
    "DNA": "dna genomics sequencing genome gene epigenetics methylation repair crispr",
    "dna": "dna genomics sequencing genome gene epigenetics methylation repair crispr",
    "RNA": "rna transcriptomics gene expression sequencing",
    "rna": "rna transcriptomics gene expression sequencing",
    "基因组": "genomics genome sequencing",
    "基因": "gene genomics genome sequencing",
    "测序": "sequencing genomics transcriptomics",
    "表观遗传": "epigenetics methylation chromatin",
    "甲基化": "methylation epigenetics dna",
    "DNA修复": "dna repair damage genome stability",
    "基因编辑": "crispr gene editing genome editing",
    "病毒": "virus viral virology infection vaccine pathogen",
    "蛋白质": "protein structure folding design proteomics",
}

LIFE_SCIENCE_TERMS = {
    "dna",
    "rna",
    "gene",
    "genes",
    "genome",
    "genomic",
    "genomics",
    "sequencing",
    "transcriptomics",
    "epigenetics",
    "methylation",
    "chromatin",
    "repair",
    "crispr",
    "virus",
    "viral",
    "virology",
    "infection",
    "vaccine",
    "pathogen",
    "protein",
    "proteomics",
    "cell",
    "cell-free",
    "cancer",
}

LIFE_SCIENCE_CHINESE_TERMS = [
    "dna",
    "rna",
    "DNA",
    "RNA",
    "基因",
    "基因组",
    "测序",
    "表观遗传",
    "甲基化",
    "基因编辑",
    "病毒",
    "蛋白质",
]

SUPPORTING_PAPER_LIMIT = 12


def normalize_arxiv_query(topic: str) -> str:
    stripped = topic.strip()
    if not stripped:
        return "agent memory"
    if re.search(r"[\u4e00-\u9fff]", topic):
        if is_agent_memory_topic(topic):
            return "agent memory large language model"
        mapped_terms: List[str] = []
        for chinese_term, english_terms in CHINESE_QUERY_TERMS.items():
            if chinese_term in topic:
                mapped_terms.extend(keyword_tokens(english_terms))
        embedded_english = keyword_tokens(clean_chinese_research_prompt(topic))
        mapped_terms.extend(embedded_english)
        if mapped_terms:
            return " ".join(dict.fromkeys(mapped_terms))
        cleaned = clean_chinese_research_prompt(stripped)
        return cleaned or stripped
    return stripped


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
    if is_life_science_topic(topic):
        tokens = life_science_topic_tokens(topic)
        if not tokens:
            tokens = keyword_tokens(normalized)
        field_query = " OR ".join(
            f'ti:"{token}" OR abs:"{token}"' for token in tokens[:8]
        )
        broad_query = " OR ".join(f"all:{token}" for token in tokens[:8])
        primary = tokens[0]
        themed = " OR ".join(f"all:{token}" for token in tokens[1:6])
        return [
            f"({field_query})",
            f"({broad_query})",
            f"(all:{primary} AND ({themed}))" if themed else f"all:{primary}",
        ]
    escaped = normalized.replace('"', "")
    tokens = keyword_tokens(escaped)
    if not tokens:
        return [f'all:"{escaped}"']
    term_query = " OR ".join(
        f'ti:"{token}" OR abs:"{token}"' for token in tokens[:6]
    )
    and_query = " AND ".join(f'all:"{token}"' for token in tokens[:4])
    return [f"({term_query})", f"({and_query})", f'all:"{escaped}"']


def build_pubmed_queries(topic: str) -> List[str]:
    tokens = life_science_topic_tokens(topic)
    if not tokens:
        return []
    current_year = datetime.now().year
    title_abs = " OR ".join(f"{token}[Title/Abstract]" for token in tokens[:8])
    broad = " OR ".join(tokens[:8])
    return [
        f"({title_abs}) AND ({current_year - 2}:{current_year}[pdat])",
        f"({title_abs})",
        f"({broad}) AND ({current_year - 2}:{current_year}[pdat])",
    ]


def clean_chinese_research_prompt(topic: str) -> str:
    cleaned = topic
    for word in CHINESE_INTENT_WORDS:
        cleaned = cleaned.replace(word, " ")
    return " ".join(cleaned.split()).strip()


def is_agent_memory_topic(topic: str) -> bool:
    lowered = topic.lower()
    english_agent = "agent" in lowered or "agents" in lowered
    english_memory = "memory" in lowered
    chinese_agent = any(term in topic for term in ["智能体", "代理", "智能代理"])
    chinese_memory = any(term in topic for term in ["记忆", "长期记忆"])
    return (english_agent or chinese_agent) and (english_memory or chinese_memory)


def is_atmospheric_optics_topic(topic: str) -> bool:
    lowered = topic.lower()
    return any(term in topic for term in ["霞光", "晚霞", "朝霞", "余晖", "大气光学"]) or any(
        term in lowered
        for term in [
            "twilight",
            "skyglow",
            "atmospheric optics",
            "sunset",
            "sunrise",
        ]
    )


def is_life_science_topic(topic: str) -> bool:
    normalized = normalize_nonrecursive_terms(topic)
    tokens = set(keyword_tokens(normalized))
    if tokens & LIFE_SCIENCE_TERMS:
        return True
    return any(term in topic for term in LIFE_SCIENCE_CHINESE_TERMS)


def is_recent_topic(topic: str) -> bool:
    lowered = topic.lower()
    return any(term in topic for term in ["最近", "近年来", "最新", "近年"]) or any(
        term in lowered for term in ["recent", "latest", "new"]
    )


def normalize_nonrecursive_terms(topic: str) -> str:
    text = clean_chinese_research_prompt(topic)
    mapped_terms: List[str] = []
    for chinese_term, english_terms in CHINESE_QUERY_TERMS.items():
        if chinese_term in topic:
            mapped_terms.extend(keyword_tokens(english_terms))
    mapped_terms.extend(keyword_tokens(text))
    return " ".join(dict.fromkeys(mapped_terms)) if mapped_terms else text


def life_science_topic_tokens(topic: str) -> List[str]:
    normalized = normalize_nonrecursive_terms(topic)
    tokens = [
        token
        for token in keyword_tokens(normalized)
        if token in LIFE_SCIENCE_TERMS or token in SHORT_KEYWORDS
    ]
    if "dna" in tokens:
        tokens.extend(["genomics", "sequencing", "genome", "gene", "epigenetics", "methylation", "repair"])
    if "virus" in tokens or "viral" in tokens:
        tokens.extend(["virology", "infection", "vaccine", "pathogen"])
    if "protein" in tokens:
        tokens.extend(["structure", "folding", "design", "proteomics"])
    return list(dict.fromkeys(tokens))


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
    result = research_search(
        topic=topic,
        max_results=max_results,
        timeout=timeout,
        candidate_pool=candidate_pool,
        min_relevance=min_relevance,
        sort_by=sort_by,
        enable_pubmed=False,
    )
    return (
        result["papers"],
        result["warnings"],
        result["rejected_papers"],
        result["queries"],
    )


def research_search(
    topic: str,
    max_results: int = 8,
    timeout: int = 25,
    candidate_pool: int = 80,
    min_relevance: float = 2.0,
    sort_by: str = "relevance",
    enable_pubmed: bool = True,
) -> Dict[str, Any]:
    warnings: List[str] = []
    arxiv_queries = build_arxiv_queries(topic)
    pubmed_queries = build_pubmed_queries(topic) if enable_pubmed and is_life_science_topic(topic) else []
    diagnostics: Dict[str, Any] = {
        "domain": infer_topic_domain(topic),
        "topic_keywords": topic_keywords(topic),
        "sources": [],
        "queries": {
            "arxiv": arxiv_queries,
            "pubmed": pubmed_queries,
        },
    }
    if candidate_pool <= 0:
        if is_agent_memory_topic(topic):
            warnings.append("candidate_pool <= 0; using fallback paper samples without arXiv network access.")
            papers = mark_importance(fallback_papers(topic, max_results), "core")
            return {
                "papers": papers,
                "supporting_papers": [],
                "warnings": warnings,
                "rejected_papers": [],
                "queries": arxiv_queries,
                "search_diagnostics": diagnostics,
            }
        warnings.append(
            "candidate_pool <= 0; offline fallback samples are only available for Agent Memory topics."
        )
        return {
            "papers": [],
            "supporting_papers": [],
            "warnings": warnings,
            "rejected_papers": [],
            "queries": arxiv_queries,
            "search_diagnostics": diagnostics,
        }

    all_candidates: Dict[str, Paper] = {}
    arxiv_candidates, arxiv_warnings = fetch_arxiv_candidates(
        topic=topic,
        queries=arxiv_queries,
        max_results=max_results,
        timeout=timeout,
        candidate_pool=candidate_pool,
        sort_by=sort_by,
    )
    warnings.extend(arxiv_warnings)
    diagnostics["sources"].append(
        {
            "source": "arxiv",
            "query_count": len(arxiv_queries),
            "candidate_count": len(arxiv_candidates),
            "warnings": arxiv_warnings,
        }
    )
    merge_candidates(all_candidates, arxiv_candidates)

    if pubmed_queries:
        pubmed_candidates, pubmed_warnings = pubmed_search(
            topic=topic,
            queries=pubmed_queries,
            timeout=timeout,
            candidate_pool=candidate_pool,
        )
        warnings.extend(pubmed_warnings)
        diagnostics["sources"].append(
            {
                "source": "pubmed",
                "query_count": len(pubmed_queries),
                "candidate_count": len(pubmed_candidates),
                "warnings": pubmed_warnings,
            }
        )
        merge_candidates(all_candidates, pubmed_candidates)

    accepted, supporting, rejected = split_ranked_papers(
        all_candidates.values(),
        max_results=max_results,
        min_relevance=min_relevance,
        supporting_limit=SUPPORTING_PAPER_LIMIT,
    )
    diagnostics["accepted_count"] = len(accepted)
    diagnostics["supporting_count"] = len(supporting)
    diagnostics["rejected_count"] = len(rejected)

    if accepted:
        if len(accepted) < max_results:
            warnings.append(
                f"Only {len(accepted)} papers passed relevance filtering; requested {max_results}."
            )
        return {
            "papers": accepted,
            "supporting_papers": supporting,
            "warnings": warnings,
            "rejected_papers": rejected,
            "queries": format_search_queries(arxiv_queries, pubmed_queries),
            "search_diagnostics": diagnostics,
        }

    if supporting:
        warnings.append(
            "No candidates reached the core relevance threshold; promoted the strongest lower-weight candidates."
        )
        promoted = mark_importance(supporting[:max_results], "core")
        remaining_supporting = mark_importance(supporting[max_results:], "supporting")
        diagnostics["accepted_count"] = len(promoted)
        diagnostics["supporting_count"] = len(remaining_supporting)
        return {
            "papers": promoted,
            "supporting_papers": remaining_supporting,
            "warnings": warnings,
            "rejected_papers": rejected,
            "queries": format_search_queries(arxiv_queries, pubmed_queries),
            "search_diagnostics": diagnostics,
        }

    if is_agent_memory_topic(topic):
        warnings.append("No arXiv candidates passed relevance filtering; using fallback paper samples.")
        fallback = mark_importance(fallback_papers(topic, max_results), "core")
        return {
            "papers": fallback,
            "supporting_papers": [],
            "warnings": warnings,
            "rejected_papers": rejected,
            "queries": format_search_queries(arxiv_queries, pubmed_queries),
            "search_diagnostics": diagnostics,
        }
    warnings.append(
        "No candidates passed relevance filtering for this topic. Try lower Min score, a larger Pool, or upload a PDF."
    )
    return {
        "papers": [],
        "supporting_papers": [],
        "warnings": warnings,
        "rejected_papers": rejected,
        "queries": format_search_queries(arxiv_queries, pubmed_queries),
        "search_diagnostics": diagnostics,
    }


def fetch_arxiv_candidates(
    topic: str,
    queries: List[str],
    max_results: int,
    timeout: int,
    candidate_pool: int,
    sort_by: str,
) -> Tuple[List[Paper], List[str]]:
    warnings: List[str] = []
    candidates: List[Paper] = []
    per_query = max(max_results, min(candidate_pool, 20))

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
                scored = score_paper_relevance(paper, topic)
                candidates.append(scored)
        except Exception as exc:
            warnings.append(f"arXiv query failed for {query} ({exc}).")
        if index < len(queries) - 1:
            time.sleep(1)
    return candidates, warnings


def pubmed_search(
    topic: str,
    queries: List[str],
    timeout: int = 25,
    candidate_pool: int = 80,
) -> Tuple[List[Paper], List[str]]:
    warnings: List[str] = []
    papers: Dict[str, Paper] = {}
    per_query = min(max(candidate_pool // max(len(queries), 1), 8), 25)
    headers = {"User-Agent": "multiple-assistant-agents-course-project/1.0"}

    for query in queries:
        try:
            search_response = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": str(per_query),
                    "sort": "pub date",
                },
                timeout=timeout,
                headers=headers,
            )
            search_response.raise_for_status()
            ids = search_response.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                continue
            summary_response = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
                timeout=timeout,
                headers=headers,
            )
            summary_response.raise_for_status()
            summaries = summary_response.json().get("result", {})
            abstracts = fetch_pubmed_abstracts(ids, timeout, headers)
            for pmid in ids:
                item = summaries.get(pmid, {})
                title = clean_text(str(item.get("title", ""))).rstrip(".")
                if not title:
                    continue
                authors = [
                    clean_text(author.get("name", ""))
                    for author in item.get("authors", [])[:8]
                    if author.get("name")
                ]
                pubdate = str(item.get("pubdate", ""))
                year_match = re.search(r"(19|20)\d{2}", pubdate)
                year = year_match.group(0) if year_match else "unknown"
                paper = Paper(
                    title=title,
                    authors=authors,
                    year=year,
                    summary=abstracts.get(pmid, "") or clean_text(str(item.get("source", ""))),
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    source="pubmed",
                    domain=infer_topic_domain(topic),
                    topic_keywords=topic_keywords(topic),
                )
                scored = score_paper_relevance(paper, topic)
                papers[pmid] = scored
        except Exception as exc:
            warnings.append(f"PubMed query failed for {query} ({exc}).")
        time.sleep(0.35)
    return list(papers.values()), warnings


def fetch_pubmed_abstracts(
    ids: List[str], timeout: int, headers: Dict[str, str]
) -> Dict[str, str]:
    if not ids:
        return {}
    try:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
            timeout=timeout,
            headers=headers,
        )
        response.raise_for_status()
        return parse_pubmed_abstracts(response.text)
    except Exception:
        return {}


def parse_pubmed_abstracts(xml_text: str) -> Dict[str, str]:
    root = ET.fromstring(xml_text)
    abstracts: Dict[str, str] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = article.findtext(".//PMID", default="")
        chunks = [
            clean_text("".join(abstract.itertext()))
            for abstract in article.findall(".//AbstractText")
        ]
        if pmid:
            abstracts[pmid] = clean_text(" ".join(chunk for chunk in chunks if chunk))
    return abstracts


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
                    source="arxiv",
                )
            )
    return papers


def score_paper_relevance(paper: Paper, topic: str) -> Paper:
    title = paper.title.lower()
    summary = paper.summary.lower()
    combined = f"{title} {summary}"
    score = 0.0
    matched_terms: List[str] = []
    agent_memory_topic = is_agent_memory_topic(topic)
    life_science_topic = is_life_science_topic(topic)

    if agent_memory_topic:
        for phrase, weight in POSITIVE_PATTERNS.items():
            if phrase in title:
                score += weight * 1.4
                matched_terms.append(phrase)
            elif phrase in summary:
                score += weight
                matched_terms.append(phrase)

    if agent_memory_topic and "agent" in combined and "memory" in combined:
        score += 2.5
        matched_terms.append("agent+memory")
    if (
        agent_memory_topic
        and ("llm" in combined or "large language model" in combined)
        and "memory" in combined
    ):
        score += 1.5
        matched_terms.append("llm+memory")

    topic_tokens = {
        token
        for token in keyword_tokens(normalize_arxiv_query(topic))
        if token not in {"recent", "research", "direction", "directions"}
    }
    if life_science_topic:
        topic_tokens.update(life_science_topic_tokens(topic))
    candidate_tokens = set(keyword_tokens(combined))
    overlap = sorted(topic_tokens & candidate_tokens)
    score += min(len(overlap), 7) * 1.25
    matched_terms.extend(overlap)
    for token in topic_tokens:
        if token in title:
            score += 1.0
        elif token in summary:
            score += 0.45

    for phrase, penalty in NEGATIVE_PATTERNS.items():
        if phrase in combined:
            score -= penalty

    if is_atmospheric_optics_topic(topic):
        atmospheric_terms = {
            "atmospheric",
            "atmosphere",
            "twilight",
            "sky",
            "skyglow",
            "sunset",
            "sunrise",
            "aerosol",
            "scattering",
            "polarization",
            "brightness",
            "optical",
            "optics",
        }
        atmospheric_overlap = sorted(atmospheric_terms & candidate_tokens)
        if atmospheric_overlap:
            score += min(len(atmospheric_overlap), 4) * 0.7
            matched_terms.extend(atmospheric_overlap)
        else:
            score -= 3.0

    if life_science_topic:
        life_overlap = sorted(LIFE_SCIENCE_TERMS & candidate_tokens)
        if life_overlap:
            score += min(len(life_overlap), 5) * 0.45
            matched_terms.extend(life_overlap)
        else:
            score -= 1.5
        if paper.source == "pubmed":
            score += 0.8
            matched_terms.append("pubmed")

    if paper.year.isdigit():
        year = int(paper.year)
        current_year = datetime.now().year
        recent_topic = is_recent_topic(topic)
        if year >= current_year - 2:
            score += 1.4 if recent_topic else 0.8
        elif year >= 2023:
            score += 0.5
        elif life_science_topic and year < current_year - 5:
            score -= 3.0
        elif year < 2020:
            score -= 0.5
        if recent_topic and year < current_year - 3:
            score -= 2.0

    paper.relevance_score = round(score, 3)
    paper.matched_terms = sorted(set(matched_terms))
    paper.domain = infer_topic_domain(topic)
    paper.topic_keywords = topic_keywords(topic)
    return paper


def merge_candidates(target: Dict[str, Paper], candidates: Iterable[Paper]) -> None:
    for paper in candidates:
        key = canonical_paper_key(paper)
        existing = target.get(key)
        if existing is None or paper.relevance_score > existing.relevance_score:
            target[key] = paper


def canonical_paper_key(paper: Paper) -> str:
    title = re.sub(r"[^a-z0-9]+", " ", paper.title.lower()).strip()
    return paper.url or title


def split_ranked_papers(
    papers: Iterable[Paper],
    max_results: int,
    min_relevance: float,
    supporting_limit: int,
) -> Tuple[List[Paper], List[Paper], List[Dict[str, Any]]]:
    ranked = sorted(
        papers,
        key=lambda item: (item.relevance_score, item.year if item.year.isdigit() else "0"),
        reverse=True,
    )
    core = [paper for paper in ranked if paper.relevance_score >= min_relevance]
    lower = [paper for paper in ranked if paper.relevance_score < min_relevance]
    accepted = mark_importance(core[:max_results], "core")
    supporting_source = core[max_results:] + lower
    supporting = mark_importance(supporting_source[:supporting_limit], "supporting")
    rejected = [
        rejected_paper_dict(paper, "below supporting relevance")
        for paper in supporting_source[supporting_limit:]
    ]
    return accepted, supporting, rejected


def mark_importance(papers: Iterable[Paper], importance: str) -> List[Paper]:
    marked = []
    for paper in papers:
        paper.importance = importance
        marked.append(paper)
    return marked


def rejected_paper_dict(paper: Paper, reason: str) -> Dict[str, Any]:
    return {
        "title": paper.title,
        "year": paper.year,
        "url": paper.url,
        "source": paper.source,
        "relevance_score": paper.relevance_score,
        "matched_terms": paper.matched_terms or [],
        "reason": reason,
    }


def format_search_queries(arxiv_queries: List[str], pubmed_queries: List[str]) -> List[str]:
    formatted = [f"arXiv: {query}" for query in arxiv_queries]
    formatted.extend(f"PubMed: {query}" for query in pubmed_queries)
    return formatted


def infer_topic_domain(topic: str) -> str:
    if is_agent_memory_topic(topic):
        return "agent-memory"
    if is_atmospheric_optics_topic(topic):
        return "atmospheric-optics"
    if is_life_science_topic(topic):
        return "life-science"
    lowered = topic.lower()
    if any(term in lowered for term in ["ai", "artificial intelligence", "machine learning", "deep learning"]):
        return "ai"
    return "general"


def topic_keywords(topic: str) -> List[str]:
    normalized = normalize_arxiv_query(topic)
    tokens = keyword_tokens(normalized)
    if is_life_science_topic(topic):
        tokens.extend(life_science_topic_tokens(topic))
    return list(dict.fromkeys(tokens))[:12]


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
    tokens: List[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", text):
        lowered = token.lower()
        if lowered in STOPWORDS:
            continue
        if len(lowered) >= 4 or lowered in SHORT_KEYWORDS:
            tokens.append(lowered)
    return tokens
