# multiple-assistant-agents

期末作业初版：AI科研助手多智能体系统。核心代码在 `code/`，方案说明见 `方案.md`。

## Quick Start

```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -r code\requirements.txt
.\.venv\Scripts\python code\main.py --topic "近年来Agent Memory有哪些研究方向？" --max-papers 5 --mock auto
```

输出文件位于 `outputs/`，长期记忆位于 `data/long_term_memory.json`。
