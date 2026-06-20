# AI科研助手调研报告：近年来Agent Memory有哪些研究方向？

## 1. 实验目标与系统概述

本系统实现了一个面向科研调研的多智能体团队。输入科研问题后，系统会进行任务规划、长期记忆检索、论文检索、摘要/PDF阅读、反思评价，并自动生成调研报告和思维导图。

## 2. 多Agent分工

| Agent | 职责 | 推理/规划方法 |
| --- | --- | --- |
| ManagerAgent | 拆解科研问题并安排流程 | Planning + CoT |
| SearchAgent | 检索arXiv论文并记录工具观察 | ReAct |
| ReadingAgent | 阅读摘要和本地PDF，提取贡献/方法 | Structured extraction |
| CriticAgent | 反思论文局限和系统风险 | Reflection |
| WriterAgent | 汇总报告、思维导图和运行日志 | Synthesis |

## 3. Manager规划结果

1. 明确研究问题与关键词；2. 检索候选论文；3. 阅读摘要和PDF片段；4. 提取贡献、方法和证据；5. 反思局限；6. 输出调研报告和思维导图。

## 4. 长期记忆检索

- 未检索到相关历史记忆，本轮将作为新的长期记忆写入。

## 5. 检索与阅读结果

| 年份 | 论文 | 主要贡献 | 方法 | 标签 |
| --- | --- | --- | --- | --- |
| 2024 | [A Survey on the Memory Mechanism of Large Language Model based Agents](https://arxiv.org/abs/2404.13501) | This survey summarizes memory modules for LLM agents, including working memory, episodic memory, semantic memory, retrieval, and reflection-driven consolidation. | Survey and taxonomy construction. | reflection, retrieval, multi-agent |
| 2023 | [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) | The paper introduces generative agents with memory streams, reflection, and planning to produce believable long-horizon behavior. | Reflection memory with verbal feedback reuse. | reflection, planning, multi-agent |
| 2023 | [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) | Reflexion lets language agents store verbal feedback from previous attempts and reuse it as memory for future decision making. | Reflection memory with verbal feedback reuse. | reflection, multi-agent |
| 2023 | [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) | MemGPT proposes virtual context management that moves information between limited context windows and longer-term storage. | Retrieval-augmented memory over external or vector storage. | long-term-memory, retrieval |
| 2023 | [MemoryBank: Enhancing Large Language Models with Long-Term Memory](https://arxiv.org/abs/2305.10250) | MemoryBank explores persistent user-level memory, forgetting, and retrieval to improve personalized LLM interactions. | Retrieval-augmented memory over external or vector storage. | long-term-memory, retrieval |

## 6. 统计工具结果

- 论文数量：5
- 年份分布：{"2023": 4, "2024": 1}
- 高频关键词：survey(2), retrieval(2), generative(2), behavior(2), reflexion(2), verbal(2), memgpt(2), context(2)

## 7. Critic反思

反思：现有论文通常存在评测场景有限、长期记忆更新策略不统一、隐私与遗忘机制讨论不足等问题。

## 8. 评分要求对齐

- Agent数量：5个，满足 >= 4。
- 推理/规划：ManagerAgent使用Planning + CoT，SearchAgent体现ReAct，CriticAgent体现Reflection。
- 记忆机制：短期记忆为本轮messages/tool_logs/notes；长期记忆为data/long_term_memory.json。
- 工具调用：arxiv_search、pdf_extract、paper_stats，共3类。
- 输出产物：survey.md、mindmap.md、run_log.json。
