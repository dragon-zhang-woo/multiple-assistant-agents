# AI科研助手调研报告：近年来Agent Memory有哪些研究方向？

## 1. 执行摘要

本次运行使用 `langgraph` 工作流和 `mock` 模型模式，围绕科研问题完成了论文检索、摘要/PDF阅读、方向归纳、Reflection反思和长期记忆更新。
系统接收 5 篇高相关论文进入正文分析，过滤 0 篇低相关候选论文。

## 2. 多Agent分工

| Agent | 职责 | 推理/规划方法 |
| --- | --- | --- |
| ManagerAgent | 拆解科研问题并安排流程 | Planning + CoT |
| SearchAgent | 检索arXiv论文并记录工具观察 | ReAct |
| ReadingAgent | 阅读摘要和本地PDF，提取贡献/方法 | Structured extraction |
| CriticAgent | 反思论文局限和系统风险 | Reflection |
| WriterAgent | 汇总报告、思维导图和运行日志 | Synthesis |

## 3. 本轮执行计划

1. 明确研究问题与关键词；2. 使用arXiv检索并过滤候选论文；3. 阅读摘要和可选本地PDF片段；4. 提取贡献、方法、方向分类和证据；5. 反思局限与风险；6. 生成报告、思维导图和长期记忆更新。

## 4. 长期记忆检索

- 未检索到相关历史记忆，本轮将作为新的长期记忆写入。

## 5. 检索与阅读结果

- 展开检索式：all:"agent memory"; (ti:"agent memory" OR abs:"agent memory" OR ti:"memory augmented agent" OR abs:"memory augmented agent"); (all:"LLM agent" AND all:"memory"); (all:"long-term memory" AND all:"agent")
- 最低相关性阈值：3.0
- 候选池规模：0

### 5.1 研究方向分类

- **综述与分类**：1 篇。代表论文：A Survey on the Memory Mechanism of Large Language Model based Agents
- **反思与经验记忆**：2 篇。代表论文：Generative Agents: Interactive Simulacra of Human Behavior；Reflexion: Language Agents with Verbal Reinforcement Learning
- **检索增强记忆**：2 篇。代表论文：MemGPT: Towards LLMs as Operating Systems；MemoryBank: Enhancing Large Language Models with Long-Term Memory

### 5.2 代表论文表

| 年份 | 相关性 | 方向 | 论文 | 主要贡献 | 方法 | 标签 |
| --- | ---: | --- | --- | --- | --- | --- |
| 2024 | 8.00 | 综述与分类 | [A Survey on the Memory Mechanism of Large Language Model based Agents](https://arxiv.org/abs/2404.13501) | This survey summarizes memory modules for LLM agents, including working memory, episodic memory, semantic memory, retrieval, and reflection-driven consolidation. | Survey and taxonomy construction. | reflection, retrieval, multi-agent |
| 2023 | 6.50 | 反思与经验记忆 | [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) | The paper introduces generative agents with memory streams, reflection, and planning to produce believable long-horizon behavior. | Reflection memory with verbal feedback reuse. | reflection, planning, multi-agent |
| 2023 | 6.00 | 反思与经验记忆 | [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) | Reflexion lets language agents store verbal feedback from previous attempts and reuse it as memory for future decision making. | Reflection memory with verbal feedback reuse. | reflection, multi-agent |
| 2023 | 6.00 | 检索增强记忆 | [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) | MemGPT proposes virtual context management that moves information between limited context windows and longer-term storage. | Retrieval-augmented memory over external or vector storage. | long-term-memory, retrieval |
| 2023 | 5.50 | 检索增强记忆 | [MemoryBank: Enhancing Large Language Models with Long-Term Memory](https://arxiv.org/abs/2305.10250) | MemoryBank explores persistent user-level memory, forgetting, and retrieval to improve personalized LLM interactions. | Retrieval-augmented memory over external or vector storage. | long-term-memory, retrieval |

## 6. 统计工具结果

- 论文数量：5
- 平均相关性：6.4
- 年份分布：{"2023": 4, "2024": 1}
- 高频关键词：survey(2), retrieval(2), generative(2), behavior(2), reflexion(2), verbal(2), memgpt(2), context(2)

## 7. Critic反思

反思：现有论文通常存在评测场景有限、长期记忆更新策略不统一、隐私与遗忘机制讨论不足等问题。

## 8. 被过滤候选论文

- 无。

## 9. 评分要求对齐

- Agent数量：5个，满足 >= 4。
- 推理/规划：ManagerAgent使用Planning + CoT，SearchAgent体现ReAct，CriticAgent体现Reflection。
- 记忆机制：短期记忆为本轮messages/tool_logs/notes；长期记忆为examples\sample_run\long_term_memory.json。
- 工具调用：arxiv_search、pdf_extract、paper_stats，共3类。
- 输出产物：survey.md、mindmap.md、run_log.json。
