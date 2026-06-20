# multiple-assistant-agents

期末作业初版：AI科研助手多智能体系统。核心代码在 `code/`，方案说明见 `方案.md`。

## Quick Start

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r code\requirements.txt
.\.venv\Scripts\python code\main.py --topic "近年来Agent Memory有哪些研究方向？" --max-papers 5 --mock auto
```

默认输出文件位于 `runs/<timestamp>/`，最近一次运行会复制到 `outputs/latest/`，长期记忆位于 `memory/long_term_memory.json`。

## DeepSeek

也可以使用 DeepSeek API key：

```bash
$env:DEEPSEEK_API_KEY="your_key_here"
.\.venv\Scripts\python code\main.py --provider deepseek --mock never --topic "近年来Agent Memory有哪些研究方向？"
```

默认 DeepSeek 模型为 `deepseek-v4-flash`，可用 `DEEPSEEK_MODEL` 覆盖。
