from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple


class BaseLLM:
    mode = "base"

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class MockResearchLLM(BaseLLM):
    mode = "mock"

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"{system_prompt}\n{user_prompt}".lower()
        if "manager" in prompt or "任务拆解" in prompt:
            return (
                "1. 明确研究问题与关键词；2. 检索候选论文；"
                "3. 阅读摘要和PDF片段；4. 提取贡献、方法和证据；"
                "5. 反思局限；6. 输出调研报告和思维导图。"
            )
        if "critic" in prompt or "reflection" in prompt:
            return (
                "反思：现有论文通常存在评测场景有限、长期记忆更新策略不统一、"
                "隐私与遗忘机制讨论不足等问题。"
            )
        if "writer" in prompt:
            return "已根据检索、阅读和反思结果整理为结构化调研报告。"
        return "已完成该步骤的结构化分析。"


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
