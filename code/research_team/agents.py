from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from research_team.llm import BaseLLM
from research_team.models import PaperAnalysis, ResearchState
from research_team.tools import (
    extract_pdf_text,
    is_agent_memory_topic,
    is_atmospheric_optics_topic,
    is_life_science_topic,
    keyword_tokens,
    paper_stats,
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


class ManagerAgent:
    name = "ManagerAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        system_prompt = (
            "You are ManagerAgent for a runnable course project. Use concise Planning. "
            "Only mention implemented capabilities: arXiv/PubMed search, local PDF extraction, "
            "paper statistics, JSON long-term memory, LangGraph workflow, and Markdown output. "
            "Do not mention Google Scholar, Semantic Scholar, Chroma, FAISS, Neo4j, citation APIs, "
            "parallel crawling, or any unimplemented tool."
        )
        user_prompt = (
            f"请为科研问题制定多Agent调研计划：{state['topic']}。"
            "要求用6条以内覆盖检索、阅读、反思、写作、记忆更新；不要写理想系统能力。"
        )
        plan = llm.invoke(system_prompt, user_prompt)
        plan = safe_manager_plan(plan, state)
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
            f"Thought: need recent papers for '{topic}'. Action: research_search.",
        )
        search_result = research_search(
            topic=topic,
            max_results=state.get("max_papers", 5),
            candidate_pool=state.get("candidate_pool", 25),
            min_relevance=state.get("min_relevance", 3.0),
            sort_by=state.get("sort_by", "relevance"),
        )
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
                "query": topic,
                "expanded_queries": queries,
                "paper_count": len(paper_dicts),
                "supporting_count": len(supporting_dicts),
                "rejected_count": len(rejected),
                "min_relevance": state.get("min_relevance", 3.0),
                "diagnostics": search_result["search_diagnostics"],
                "warnings": warnings,
            }
        )
        add_message(
            state,
            self.name,
            "Observe: retrieved "
            f"{len(paper_dicts)} core papers and {len(supporting_dicts)} supporting papers. "
            "Summarize: candidates are ready for ReadingAgent.",
        )
        return state


class ReadingAgent:
    name = "ReadingAgent"

    def run(self, state: ResearchState, llm: BaseLLM) -> ResearchState:
        analyses: List[Dict[str, Any]] = []
        for paper in state.get("papers", []):
            analyses.append(self._analyze_paper(paper, state["topic"], llm).to_dict())

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

    def _analyze_paper(
        self, paper: Dict[str, Any], topic: str, llm: BaseLLM
    ) -> PaperAnalysis:
        if llm.mode != "mock":
            llm_result = self._analyze_with_llm(paper, topic, llm)
            if llm_result is not None:
                return llm_result
        return self._fallback_analyze_paper(paper, topic)

    def _analyze_with_llm(
        self, paper: Dict[str, Any], topic: str, llm: BaseLLM
    ) -> PaperAnalysis | None:
        system_prompt = (
            "You are ReadingAgent. Extract only what is supported by the title and abstract. "
            "Return strict JSON with keys: contribution, method, limitations, tags, category. "
            "The category must describe the research direction for the user's topic, not a fixed domain. "
            "Do not use Agent Memory, LLM agent, retrieval memory, or long-term memory categories unless "
            "the title/abstract and user topic are actually about those concepts. Use Chinese, concise wording."
        )
        user_prompt = json.dumps(
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
        if llm.mode == "mock":
            critique = build_fallback_critique(state)
            state["critique_summary"] = critique
            add_message(state, self.name, critique)
            return state
        system_prompt = (
            "You are CriticAgent. Use Reflection to identify limits and risks. "
            "Stay within the provided analyses; do not invent papers, tools, or experiments."
        )
        analysis_payload = json.dumps(
            state.get("paper_analyses", []), ensure_ascii=False, indent=2
        )
        user_prompt = (
            f"用户主题：{state.get('topic', '')}\n"
            "请基于以下结构化阅读结果做反思，输出不超过6条要点：\n"
            f"{analysis_payload}\n"
            f"角度：{critic_angles_for_topic(state.get('topic', ''))}。"
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
        (
            f"本次运行使用 `{state.get('workflow_engine', 'unknown')}` 工作流和 "
            f"`{state.get('llm_mode', 'unknown')}` 模型模式，围绕科研问题完成了论文检索、"
            "摘要/PDF阅读、方向归纳、Reflection反思和长期记忆更新。"
        ),
        (
            f"系统接收 {stats.get('paper_count', 0)} 篇高相关论文进入正文分析，"
            f"保留 {len(supporting)} 篇低权重补充候选，过滤 {len(rejected)} 篇低相关候选论文。"
        ),
        "",
        "## 2. 多Agent分工",
        "",
        "| Agent | 职责 | 推理/规划方法 |",
        "| --- | --- | --- |",
        "| ManagerAgent | 拆解科研问题并安排流程 | Planning + CoT |",
        "| SearchAgent | 检索arXiv/PubMed论文并记录工具观察 | ReAct |",
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
            "- 工具调用：research_search（arXiv/PubMed）、pdf_extract、paper_stats，共3类。",
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
        "      arXiv/PubMed检索",
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
