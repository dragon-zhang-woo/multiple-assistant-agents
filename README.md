# multiple-assistant-agents

期末作业初版：AI科研助手多智能体系统。核心代码在 `code/`，方案说明见 `方案.md`。

## CLI Quick Start

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

## Web Workbench

`web/` 是 Claude-like 多 Agent 科研协作助手前端，使用 Next.js App Router、React、TypeScript、Tailwind CSS 和 shadcn/ui 风格组件。它通过 Next API 复用 `code/` 中的 Python 多 Agent workflow，并使用 SSE 显示 Planner、Scholar、Reader、Critic、Writer 的阶段进度。

```bash
cd web
npm install
npm run dev
```

打开 `http://localhost:3000` 后，可以在左侧选择 provider、模型、论文数量、候选池、相关性阈值和排序方式；中间输入科研问题并可上传 PDF；右侧会显示 `survey`、`mindmap`、文献矩阵和 `run_log`。界面支持亮色/暗色主题。

### Web API key

Web 端不在浏览器保存 API key。请在 `web/.env.local` 或启动 dev server 的 PowerShell 环境中配置服务端变量：

```powershell
Copy-Item .env.local.example .env.local
notepad .env.local
```

或直接在当前 PowerShell 设置：

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"

$env:DASHSCOPE_API_KEY="your_key_here"
$env:DASHSCOPE_MODEL="qwen-turbo"
```

保存或设置变量后，重启 `npm run dev`。左侧 `Server key` 会显示 `configured` 或 `missing`。`web/.env.local`、上传 PDF、运行缓存和构建产物均已加入 `.gitignore`。

校验命令：

```bash
npm run lint
npm run typecheck
npm run build
```
