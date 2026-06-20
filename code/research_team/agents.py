from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from research_team.llm import BaseLLM
from research_team.models import PaperAnalysis, ResearchState
from research_team.tools import arxiv_search, extract_pdf_text, paper_stats


def add_message(state: ResearchState, speaker: str, content: str) -> None:
    state.setdefault("messages", []).append(
        {
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    )


class ManagerAgent:
    name = "ManagerAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        system_prompt = (
            "You are ManagerAgent for a runnable course project. Use concise Planning. "
            "Only mention implemented capabilities: arXiv search, local PDF extraction, "
            "paper statistics, JSON long-term memory, LangGraph workflow, and Markdown output. "
            "Do not mention Google Scholar, Semantic Scholar, Chroma, FAISS, Neo4j, citation APIs, "
            "parallel crawling, or any unimplemented tool."
        )
        user_prompt = (
            f"请为科研问题制定多Agent调研计划：{state['topic']}。"
            "要求用6条以内覆盖检索、阅读、反思、写作、记忆更新；不要写理想系统能力。"
        )
        plan = llm.invoke(system_prompt, user_prompt)
        state["plan"] = plan
        add_message(state, self.name, f"Planning result: {plan}")
        return state


class SearchAgent:
    name = "SearchAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        topic = state["topic"]
        add_message(
            state,
            self.name,
            f"Thought: need recent papers for '{topic}'. Action: arxiv_search.",
        )
        papers, warnings, rejected, queries = arxiv_search(
            topic=topic,
            max_results=state.get("max_papers", 5),
            candidate_pool=state.get("candidate_pool", 25),
            min_relevance=state.get("min_relevance", 3.0),
            sort_by=state.get("sort_by", "relevance"),
        )
        state.setdefault("warnings", []).extend(warnings)
        paper_dicts = [paper.to_dict() for paper in papers]
        state["papers"] = paper_dicts
        state["rejected_papers"] = rejected
        state["search_queries"] = queries
        state.setdefault("tool_logs", []).append(
            {
                "tool": "arxiv_search",
                "query": topic,
                "expanded_queries": queries,
                "paper_count": len(paper_dicts),
                "rejected_count": len(rejected),
                "min_relevance": state.get("min_relevance", 3.0),
                "warnings": warnings,
            }
        )
        add_message(
            state,
            self.name,
            "Observe: retrieved "
            f"{len(paper_dicts)} papers. Summarize: candidates are ready for ReadingAgent.",
        )
        return state


class ReadingAgent:
    name = "ReadingAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        analyses: List[Dict[str, Any]] = []
        for paper in state.get("papers", []):
            analyses.append(self._analyze_paper(paper, llm).to_dict())

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
            f"Read {len(state.get('papers', []))} paper abstracts and {len(pdf_notes)} local PDFs.",
        )
        return state

    def _analyze_paper(self, paper: Dict[str, Any], llm: BaseLLM) -> PaperAnalysis:
        if llm.mode != "mock":
            llm_result = self._analyze_with_llm(paper, llm)
            if llm_result is not None:
                return llm_result
        return self._fallback_analyze_paper(paper)

    def _analyze_with_llm(
        self, paper: Dict[str, Any], llm: BaseLLM
    ) -> PaperAnalysis | None:
        system_prompt = (
            "You are ReadingAgent. Extract only what is supported by the title and abstract. "
            "Return strict JSON with keys: contribution, method, limitations, tags, category. "
            "category must be one of: 综述与分类, 长期记忆架构, 检索增强记忆, 反思与经验记忆, "
            "安全隐私与评测, 其他相关方向. Use Chinese, concise wording."
        )
        user_prompt = json.dumps(
            {
                "title": paper.get("title", ""),
                "year": paper.get("year", ""),
                "abstract": paper.get("summary", ""),
                "matched_terms": paper.get("matched_terms", []),
                "relevance_score": paper.get("relevance_score", 0),
            },
            ensure_ascii=False,
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
        return PaperAnalysis(
            title=paper.get("title", ""),
            year=str(paper.get("year", "unknown")),
            url=paper.get("url", ""),
            contribution=str(data.get("contribution", "")).strip()
            or first_sentence(paper.get("summary", "")),
            method=str(data.get("method", "")).strip()
            or infer_method(paper.get("title", ""), paper.get("summary", "")),
            limitations=str(data.get("limitations", "")).strip()
            or "仅基于摘要分析，尚需全文验证。",
            tags=[str(tag) for tag in tags[:5]] or infer_tags(paper.get("title", "")),
            source=paper.get("source", "arxiv"),
            category=str(data.get("category", "")).strip()
            or infer_category(paper.get("title", ""), paper.get("summary", "")),
            relevance_score=float(paper.get("relevance_score", 0) or 0),
        )

    def _fallback_analyze_paper(self, paper: Dict[str, Any]) -> PaperAnalysis:
        title = paper.get("title", "")
        summary = paper.get("summary", "")
        tags = infer_tags(title + " " + summary)
        contribution = first_sentence(summary) or "The paper contributes to agent research."
        method = infer_method(title, summary)
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
            category=infer_category(title, summary),
            relevance_score=float(paper.get("relevance_score", 0) or 0),
        )


class CriticAgent:
    name = "CriticAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        system_prompt = (
            "You are CriticAgent. Use Reflection to identify limits and risks. "
            "Stay within the provided analyses; do not invent papers, tools, or experiments."
        )
        analysis_payload = json.dumps(
            state.get("paper_analyses", []), ensure_ascii=False, indent=2
        )
        user_prompt = (
            "请基于以下结构化阅读结果做反思，输出不超过6条要点：\n"
            f"{analysis_payload}\n"
            "角度：摘要证据不足、实验验证、长期记忆更新、隐私安全、应用落地。"
        )
        critique = llm.invoke(system_prompt, user_prompt)
        state["critique_summary"] = critique
        add_message(state, self.name, critique)
        return state


class WriterAgent:
    name = "WriterAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        output_dir = Path(state.get("output_dir", "outputs"))
        output_dir.mkdir(parents=True, exist_ok=True)

        state["stats"] = paper_stats(state.get("papers", []))
        state.setdefault("tool_logs", []).append(
            {"tool": "paper_stats", "result": state["stats"]}
        )

        report = build_survey_markdown(state)
        mindmap = build_mindmap_markdown(state)
        report_path = output_dir / "survey.md"
        mindmap_path = output_dir / "mindmap.md"
        report_path.write_text(report, encoding="utf-8")
        mindmap_path.write_text(mindmap, encoding="utf-8")
        state["report_path"] = str(report_path)
        state["mindmap_path"] = str(mindmap_path)
        add_message(state, self.name, "Wrote survey.md and mindmap.md.")
        return state


def infer_tags(text: str) -> List[str]:
    lowered = text.lower()
    tags: List[str] = []
    candidates = {
        "long-term-memory": ["long-term", "persistent", "memorybank", "memgpt"],
        "reflection": ["reflection", "reflexion", "feedback"],
        "planning": ["planning", "plan"],
        "retrieval": ["retrieval", "retrieve", "rag", "vector"],
        "multi-agent": ["multi-agent", "agents", "generative agents"],
        "benchmark": ["benchmark", "evaluation", "evaluate"],
    }
    for tag, keywords in candidates.items():
        if any(keyword in lowered for keyword in keywords):
            tags.append(tag)
    return tags or ["agent-memory"]


def infer_category(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
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


def infer_method(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
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
    categories = group_by_category(analyses)
    rejected = state.get("rejected_papers", [])
    stats = state.get("stats", {})
    lines: List[str] = [
        f"# AI科研助手调研报告：{state['topic']}",
        "",
        "## 1. 执行摘要",
        "",
        (
            f"本次运行使用 `{state.get('workflow_engine', 'unknown')}` 工作流和 "
            f"`{state.get('llm_mode', 'unknown')}` 模型模式，围绕科研问题完成了论文检索、"
            "摘要/PDF阅读、方向归纳、Reflection反思和长期记忆更新。"
        ),
        (
            f"系统接收 {stats.get('paper_count', 0)} 篇高相关论文进入正文分析，"
            f"过滤 {len(rejected)} 篇低相关候选论文。"
        ),
        "",
        "## 2. 多Agent分工",
        "",
        "| Agent | 职责 | 推理/规划方法 |",
        "| --- | --- | --- |",
        "| ManagerAgent | 拆解科研问题并安排流程 | Planning + CoT |",
        "| SearchAgent | 检索arXiv论文并记录工具观察 | ReAct |",
        "| ReadingAgent | 阅读摘要和本地PDF，提取贡献/方法 | Structured extraction |",
        "| CriticAgent | 反思论文局限和系统风险 | Reflection |",
        "| WriterAgent | 汇总报告、思维导图和运行日志 | Synthesis |",
        "",
        "## 3. 本轮执行计划",
        "",
        state.get("plan", ""),
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

    lines.extend(
        [
            "",
            "## 5. 检索与阅读结果",
            "",
            f"- 展开检索式：{'; '.join(state.get('search_queries', []))}",
            f"- 最低相关性阈值：{state.get('min_relevance', 0)}",
            f"- 候选池规模：{state.get('candidate_pool', 0)}",
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
            "| 年份 | 相关性 | 方向 | 论文 | 主要贡献 | 方法 | 标签 |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for item in analyses:
        lines.append(
            "| {year} | {score:.2f} | {category} | [{title}]({url}) | {contribution} | {method} | {tags} |".format(
                year=item.get("year", ""),
                score=float(item.get("relevance_score", 0) or 0),
                category=escape_pipe(item.get("category", "")),
                title=escape_pipe(item.get("title", "")),
                url=item.get("url", ""),
                contribution=escape_pipe(item.get("contribution", "")),
                method=escape_pipe(item.get("method", "")),
                tags=", ".join(item.get("tags", [])),
            )
        )

    lines.extend(
        [
            "",
            "## 6. 统计工具结果",
            "",
            f"- 论文数量：{stats.get('paper_count', 0)}",
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
            "## 8. 被过滤候选论文",
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
            "## 9. 评分要求对齐",
            "",
            "- Agent数量：5个，满足 >= 4。",
            "- 推理/规划：ManagerAgent使用Planning + CoT，SearchAgent体现ReAct，CriticAgent体现Reflection。",
            f"- 记忆机制：短期记忆为本轮messages/tool_logs/notes；长期记忆为{state.get('memory_path', '')}。",
            "- 工具调用：arxiv_search、pdf_extract、paper_stats，共3类。",
            "- 输出产物：survey.md、mindmap.md、run_log.json。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_mindmap_markdown(state: ResearchState) -> str:
    categories = group_by_category(state.get("paper_analyses", []))
    lines = [
        f"# Mindmap：{state['topic']}",
        "",
        "```mermaid",
        "mindmap",
        f"  root(({state['topic']}))",
        "    Agent团队",
        "      ManagerAgent",
        "      SearchAgent",
        "      ReadingAgent",
        "      CriticAgent",
        "      WriterAgent",
        "    记忆机制",
        "      短期记忆",
        "      长期JSON向量记忆",
        "    工具调用",
        "      arXiv检索",
        "      PDF读取",
        "      统计分析",
        "    研究主题",
    ]
    for category, items in categories.items():
        lines.append(f"      {category}")
        for item in items[:3]:
            title = item.get("title", "paper").replace("(", "").replace(")", "")
            lines.append(f"        {title[:48]}")
    lines.extend(["```", ""])
    return "\n".join(lines)


def escape_pipe(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def group_by_category(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item.get("category", "未分类"), []).append(item)
    return grouped
