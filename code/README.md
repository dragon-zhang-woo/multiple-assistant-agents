# AI Research Agent Team

期末作业初版：一个面向科研调研的多智能体系统。输入科研问题后，系统会完成任务规划、长期记忆检索、arXiv/PubMed论文检索、摘要/PDF阅读、Reflection反思，并生成 `survey.md` 与 `mindmap.md`。

## 实验要求对齐

- 多智能体数量：5个，分别是 `ManagerAgent`、`SearchAgent`、`ReadingAgent`、`CriticAgent`、`WriterAgent`。
- 推理/规划方法：`ManagerAgent` 使用 Planning + CoT；`SearchAgent` 使用 ReAct 风格的 Thought/Action/Observe；`CriticAgent` 使用 Reflection。
- 记忆机制：短期记忆保存在 `messages`、`tool_logs`、`pdf_notes`；长期记忆保存在 `data/long_term_memory.json`。
- 工具调用：`research_search`（arXiv/PubMed）、`pdf_extract`、`paper_stats`，另包含 `memory_retrieve` 和 `memory_update`。
- 框架：优先使用 LangGraph；如果当前环境未安装 LangGraph，会顺序执行同一工作流并在日志中记录 warning，便于课堂演示。

## 安装依赖

```bash
pip install -r code/requirements.txt
```

## 运行方式

无 API key 的演示模式：

```bash
python code/main.py --topic "近年来Agent Memory有哪些研究方向？" --max-papers 5 --mock auto
```

带本地 PDF：

```bash
python code/main.py --topic "Agent Memory综述" --pdf "7-Agent-lab(1).pdf" --mock auto
```

真实 DeepSeek 模型模式：

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
.\.venv\Scripts\python code\main.py --provider deepseek --topic "近年来Agent Memory有哪些研究方向？" --max-papers 5 --mock never
```

真实 DashScope/Qwen 模型模式：

```powershell
$env:DASHSCOPE_API_KEY="your_key_here"
.\.venv\Scripts\python code\main.py --provider dashscope --topic "近年来Agent Memory有哪些研究方向？" --max-papers 5 --mock never
```

检索质量参数（`--max-papers` 为核心论文数，报告还会保留低权重补充候选）：

```bash
python code/main.py --topic "近年来Agent Memory有哪些研究方向？" --candidate-pool 30 --min-relevance 3.5 --sort relevance
```

离线稳定样例：

```bash
python code/main.py --topic "近年来Agent Memory有哪些研究方向？" --candidate-pool 0 --mock always
```

查看配置但不运行：

```bash
python code/main.py --dry-run-config --provider deepseek --mock never
```

可选环境变量：

- `DEEPSEEK_API_KEY`：DeepSeek API 密钥。
- `DEEPSEEK_MODEL`：默认 `deepseek-v4-flash`。
- `DEEPSEEK_BASE_URL`：默认 `https://api.deepseek.com`。
- `DASHSCOPE_API_KEY`：真实模型调用密钥。
- `DASHSCOPE_MODEL`：默认 `qwen-turbo`。
- `DASHSCOPE_BASE_URL`：默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

Provider 选择：

- `--provider auto`：优先使用 `DEEPSEEK_API_KEY`，其次使用 `DASHSCOPE_API_KEY`，都没有则按 `--mock` 策略兜底。
- `--provider deepseek`：只使用 DeepSeek。
- `--provider dashscope`：只使用 DashScope/Qwen。

## 输出文件

- `runs/<timestamp>/survey.md`：调研报告。
- `runs/<timestamp>/mindmap.md`：Mermaid 思维导图。
- `runs/<timestamp>/run_log.json`：完整运行状态、工具日志和 warning。
- `outputs/latest/`：最近一次运行副本，默认被 git 忽略。
- `memory/long_term_memory.json`：长期记忆库，默认被 git 忽略。
- `examples/sample_run/`：仓库内提交的稳定样例输出。

## 目录说明

```text
code/
  main.py
  requirements.txt
  README.md
  research_team/
    agents.py
    llm.py
    memory.py
    models.py
    tools.py
    workflow.py
```
