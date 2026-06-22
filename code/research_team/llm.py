from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple


class BaseLLM:
    mode = "base"

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class MockResearchLLM(BaseLLM):
    """Deterministic mock that understands structured prompts used by the
    upgraded ManagerAgent (CoT topic profile), SearchAgent (ReAct decision),
    and CriticAgent (Reflexion decision)."""

    mode = "mock"

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"{system_prompt}\n{user_prompt}"
        lowered = prompt.lower()

        # Topic-profile JSON requested by ManagerAgent (CoT step 2).
        if "topic_profile_json" in lowered or "topic profile" in lowered:
            return self._mock_topic_profile(prompt)

        # ReAct decision JSON requested by SearchAgent each iteration.
        if "react_decision_json" in lowered:
            return self._mock_react_decision(prompt)

        # Reflexion decision JSON requested by CriticAgent.
        if "critic_decision_json" in lowered:
            return self._mock_critic_decision(prompt)

        # Structured paper extraction requested by ReadingAgent.
        if "reading_extract_json" in lowered:
            return self._mock_reading_extract(prompt)

        # Writer-level rewrites (executive summary, narratives) requested by
        # WriterAgent.
        if "writer_section_json" in lowered:
            return self._mock_writer_section(prompt)

        # Query rewrite suggestions requested by tools.query_rewrite_llm.
        if "query_rewrite_json" in lowered:
            return self._mock_query_rewrite(prompt)

        if "manager" in lowered or "任务拆解" in lowered or "planning" in lowered:
            return (
                "Thought: 用户问题需要拆解为关键词识别、检索、阅读、反思、汇总五步。\n"
                "1. 明确研究问题与关键词；2. 使用arXiv/PubMed检索并过滤候选论文；"
                "3. 阅读摘要和可选本地PDF片段；4. 提取贡献、方法、方向分类和证据；"
                "5. CriticAgent反思证据充分性并决定是否回到检索；"
                "6. WriterAgent生成报告、思维导图与长期记忆更新。"
            )
        if "critic" in lowered or "reflection" in lowered:
            return (
                "反思：现有论文通常存在评测场景有限、方法细节不足、证据覆盖不全等问题，"
                "如果论文数量较少建议补充关键词重新检索。"
            )
        if "writer" in lowered:
            return "已根据检索、阅读和反思结果整理为结构化调研报告。"
        return "已完成该步骤的结构化分析。"

    @staticmethod
    def _extract_topic(prompt: str) -> str:
        """Best-effort pull of the user topic embedded in a user prompt."""
        marker = "用户主题"
        idx = prompt.find(marker)
        if idx == -1:
            idx = prompt.find("topic")
        if idx == -1:
            return ""
        tail = prompt[idx : idx + 200]
        for sep in ["：", ":", "=", "\n"]:
            if sep in tail:
                candidate = tail.split(sep, 1)[1]
                return candidate.strip().splitlines()[0][:120]
        return ""

    def _mock_topic_profile(self, prompt: str) -> str:
        topic = self._extract_topic(prompt)
        keywords = _mock_keywords_for_topic(topic)
        profile = {
            "english_keywords": keywords,
            "domain": _mock_domain_for_topic(topic),
            "arxiv_query_hint": " OR ".join(keywords[:6]),
            "pubmed_query_hint": " OR ".join(
                f"{kw}[Title/Abstract]" for kw in keywords[:6]
            ),
            "expected_directions": [
                f"{topic or 'topic'}的基础研究",
                f"{topic or 'topic'}的应用与产业化",
                f"{topic or 'topic'}的方法与机制",
            ],
            "thoughts": (
                f"CoT: 用户问题指向 '{topic or 'topic'}'，需要将中文表达映射到英文检索词，"
                "并覆盖基础研究、应用、方法三个方向。"
            ),
        }
        return json.dumps(profile, ensure_ascii=False)

    def _mock_react_decision(self, prompt: str) -> str:
        # Mock chooses to stop after first observation to keep tests fast and
        # deterministic. Real LLM is free to refine.
        decision = {
            "thought": "已经拿到首批候选论文，覆盖度可接受，停止检索进入阅读。",
            "action": "stop",
            "refined_keywords": [],
        }
        # If the prompt explicitly says "no papers", retry once with extras.
        if "no papers" in prompt.lower() or "0 papers" in prompt.lower():
            decision = {
                "thought": "首轮未命中，扩展英文同义词后再检索。",
                "action": "search",
                "refined_keywords": ["review", "survey", "method"],
            }
        return json.dumps(decision, ensure_ascii=False)

    def _mock_critic_decision(self, prompt: str) -> str:
        # Default: do not retry, write directly.
        decision = {
            "reflection": (
                "反思：摘要证据基本覆盖核心方向，但方法细节与可复现性仍需全文核查；"
                "建议在Writer阶段标注证据强度。"
            ),
            "needs_more_search": False,
            "suggested_keywords": [],
        }
        if "paper_count=0" in prompt or "papers: 0" in prompt.lower():
            decision = {
                "reflection": "反思：本轮没有有效论文，建议补充关键词并重试检索。",
                "needs_more_search": True,
                "suggested_keywords": ["review", "mechanism"],
            }
        return json.dumps(decision, ensure_ascii=False)

    def _mock_reading_extract(self, prompt: str) -> str:
        topic = self._extract_topic(prompt)
        title = self._extract_field(prompt, "title") or "paper"
        abstract = self._extract_field(prompt, "abstract") or ""
        snippet = abstract[:120] if abstract else title[:80]
        tags = []
        for kw in _mock_keywords_for_topic(topic):
            if kw.lower() in (title + " " + abstract).lower():
                tags.append(kw)
            if len(tags) >= 4:
                break
        if not tags:
            tags = ["survey", "method"]
        analysis = {
            "contribution": f"该论文围绕「{topic or 'topic'}」提供了基于摘要的证据：{snippet}",
            "method": "Abstract-driven structured analysis enriched with LLM-extracted keywords.",
            "limitations": "仅基于摘要分析，方法细节、统计效力与可复现性仍需全文验证。",
            "tags": tags[:5],
            "category": _mock_category_for_topic(topic),
        }
        return json.dumps(analysis, ensure_ascii=False)

    def _mock_writer_section(self, prompt: str) -> str:
        topic = self._extract_topic(prompt)
        section = self._extract_field(prompt, "section") or "executive_summary"
        if section == "executive_summary":
            payload = {
                "executive_summary": (
                    f"围绕「{topic or 'topic'}」，本轮调研梳理了基础研究、方法机制与应用三条主线，"
                    "并通过 ReAct 检索循环与 Reflexion 反思保证证据覆盖度；后续工作可重点关注全文实验设计与可复现性。"
                )
            }
        elif section == "direction_narratives":
            payload = {
                "direction_narratives": {
                    "基础研究": "围绕主题的机制层面证据已初步覆盖，但缺乏跨实验室验证。",
                    "方法机制": "现有方法主要是摘要级抽取与小样本分析，对复杂场景泛化能力不足。",
                    "应用落地": "应用案例稀疏，需要结合产业数据评估收益。",
                }
            }
        elif section == "future_work":
            payload = {
                "future_work": [
                    "扩展数据集并补充跨机构的独立验证。",
                    "对比不同方法的统计效力与误差棒。",
                    "结合本地 PDF 全文重新评估关键证据。",
                ]
            }
        elif section == "glossary":
            payload = {
                "glossary": [
                    {"term": "ReAct", "explain": "推理与行动交替的 Agent 推理框架。"},
                    {"term": "Reflexion", "explain": "通过反思与重试改进 Agent 决策。"},
                    {"term": "RAG", "explain": "检索增强生成，用外部知识补充语言模型。"},
                ]
            }
        else:
            payload = {section: f"本节摘要：围绕「{topic or 'topic'}」的结构化叙事。"}
        return json.dumps(payload, ensure_ascii=False)

    def _mock_query_rewrite(self, prompt: str) -> str:
        topic = self._extract_topic(prompt)
        keywords = _mock_keywords_for_topic(topic)
        return json.dumps(
            {
                "keywords": keywords[:6],
                "rationale": "Mock LLM: 复用 topic 关键词扩展，覆盖学名与方法关键词。",
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _extract_field(prompt: str, field: str) -> str:
        marker = f'"{field}"'
        idx = prompt.find(marker)
        if idx == -1:
            return ""
        tail = prompt[idx + len(marker):]
        sep = tail.find(":")
        if sep == -1:
            return ""
        body = tail[sep + 1:].lstrip()
        if body.startswith('"'):
            end = body.find('"', 1)
            if end != -1:
                return body[1:end]
        return body.split(",")[0].strip().strip('"')


def _mock_keywords_for_topic(topic: str) -> List[str]:
    """Tiny offline keyword expander so mock-mode tests still get useful
    English search terms for arbitrary Chinese topics (e.g. 虫草菌)."""
    lowered = topic.lower()
    if "虫草" in topic or "cordyceps" in lowered:
        return [
            "cordyceps",
            "ophiocordyceps",
            "entomopathogenic fungi",
            "cordycepin",
            "mycelium",
            "bioactive metabolite",
        ]
    if "agent" in lowered and "memory" in lowered:
        return ["agent memory", "long-term memory", "llm agent", "retrieval", "reflection"]
    if "霞光" in topic or "twilight" in lowered:
        return ["twilight sky", "atmospheric optics", "aerosol", "scattering", "polarization"]
    if "dna" in lowered or "基因" in topic:
        return ["dna", "genomics", "sequencing", "epigenetics", "methylation"]
    # Generic fallback: best effort tokenize.
    tokens = [t for t in topic.split() if len(t) >= 3]
    return (tokens or ["research", "review"])[:6]


def _mock_domain_for_topic(topic: str) -> str:
    lowered = topic.lower()
    if "虫草" in topic or "cordyceps" in lowered:
        return "life-science"
    if "agent" in lowered and "memory" in lowered:
        return "agent-memory"
    if "霞光" in topic or "twilight" in lowered:
        return "atmospheric-optics"
    if "dna" in lowered or "基因" in topic or "病毒" in topic:
        return "life-science"
    return "general"


def _mock_category_for_topic(topic: str) -> str:
    domain = _mock_domain_for_topic(topic)
    if domain == "life-science":
        return "生命科学相关研究"
    if domain == "agent-memory":
        return "智能体记忆与反思"
    if domain == "atmospheric-optics":
        return "大气光学相关研究"
    return "相关研究"


@dataclass
class DashScopeLLM(BaseLLM):
    client: object
    system_message_cls: object
    human_message_cls: object
    mode: str = "dashscope"

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            self.system_message_cls(content=system_prompt),
            self.human_message_cls(content=user_prompt),
        ]
        response = self.client.invoke(messages)
        return str(response.content)


def build_llm(
    mock_mode: str = "auto", provider: str = "auto"
) -> Tuple[BaseLLM, List[str]]:
    """Build an OpenAI-compatible LLM, falling back to a deterministic mock."""
    warnings: List[str] = []

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    if mock_mode == "always":
        return MockResearchLLM(), warnings

    resolved = resolve_provider(provider)
    if not resolved:
        message = missing_key_message(provider)
        if mock_mode == "never":
            raise RuntimeError(message)
        warnings.append(f"{message} Using deterministic mock LLM.")
        return MockResearchLLM(), warnings

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        if mock_mode == "never":
            raise RuntimeError(
                "langchain-openai and langchain-core are required for real API mode."
            ) from exc
        warnings.append(
            "LangChain OpenAI packages are not installed; using deterministic mock LLM."
        )
        return MockResearchLLM(), warnings

    provider_name, api_key, model, base_url = resolved
    client = ChatOpenAI(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0.2,
    )
    llm = DashScopeLLM(client, SystemMessage, HumanMessage)
    llm.mode = provider_name
    return llm, warnings


def resolve_provider(provider: str) -> Optional[Tuple[str, str, str, str]]:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    dashscope_key = os.getenv("DASHSCOPE_API_KEY")

    if provider == "deepseek":
        if not deepseek_key:
            return None
        return (
            "deepseek",
            deepseek_key,
            os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    if provider == "dashscope":
        if not dashscope_key:
            return None
        return (
            "dashscope",
            dashscope_key,
            os.getenv("DASHSCOPE_MODEL", "qwen-turbo"),
            os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
        )

    if deepseek_key:
        return (
            "deepseek",
            deepseek_key,
            os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    if dashscope_key:
        return (
            "dashscope",
            dashscope_key,
            os.getenv("DASHSCOPE_MODEL", "qwen-turbo"),
            os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
        )
    return None


def missing_key_message(provider: str) -> str:
    if provider == "deepseek":
        return "DEEPSEEK_API_KEY is required for --provider deepseek, or use --mock always."
    if provider == "dashscope":
        return "DASHSCOPE_API_KEY is required for --provider dashscope, or use --mock always."
    return (
        "No LLM API key found. Set DEEPSEEK_API_KEY or DASHSCOPE_API_KEY, "
        "or use --mock always."
    )
