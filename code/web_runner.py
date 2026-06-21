from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from research_team.workflow import run_research_workflow


def main() -> int:
    try:
        request = scrub_surrogates(json.loads(sys.stdin.read() or "{}"))
        configure_model_env(request)
        for event in initial_agent_events():
            emit(event)
        state = run_web_workflow(request)
        emit_completion_events(state)
        return 0
    except Exception as exc:
        emit(
            {
                "type": "run.error",
                "message": sanitize_error(str(exc)),
                "timestamp": now(),
            }
        )
        return 1


def run_web_workflow(request: Dict[str, Any]) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    run_name = sanitize_run_name(str(request.get("runName") or timestamp_name()))
    provider = normalize_provider(str(request.get("provider") or "auto"))
    mock_mode = normalize_mock_mode(provider, str(request.get("mockMode") or "auto"))
    output_dir = repo_root / "runs" / f"web-{run_name}"
    memory_path = repo_root / "memory" / "web_long_term_memory.json"
    latest_dir = repo_root / "outputs" / "latest-web"
    pdf_paths = [Path(path) for path in request.get("pdfPaths", []) if path]

    return run_research_workflow(
        topic=str(request.get("topic") or "近年来Agent Memory有哪些研究方向？"),
        max_papers=to_int(request.get("maxPapers"), 8),
        candidate_pool=to_int(request.get("candidatePool"), 80),
        min_relevance=to_float(request.get("minRelevance"), 2.0),
        sort_by=str(request.get("sort") or "relevance"),
        pdf_paths=pdf_paths,
        output_dir=output_dir,
        memory_path=memory_path,
        mock_mode=mock_mode,
        provider="auto" if provider == "mock" else provider,
        run_name=run_name,
        latest_dir=latest_dir,
        event_sink=emit,
    )


def configure_model_env(request: Dict[str, Any]) -> None:
    provider = normalize_provider(str(request.get("provider") or "auto"))
    model = str(request.get("model") or "").strip()
    if not model:
        return
    if provider == "deepseek":
        os.environ["DEEPSEEK_MODEL"] = model
    if provider == "dashscope":
        os.environ["DASHSCOPE_MODEL"] = model


def emit_completion_events(state: Dict[str, Any]) -> None:
    artifacts = build_artifacts(state)
    for artifact in artifacts:
        emit({"type": "artifact.upsert", "artifact": artifact})

    citations = [
        paper.get("title", "")
        for paper in state.get("papers", [])[:3]
        if paper.get("title")
    ]
    emit(
        {
            "type": "message.done",
            "message": {
                "id": f"assistant-{state.get('run_name', timestamp_name())}",
                "role": "assistant",
                "agentId": "writer",
                "createdAt": datetime.now().strftime("%H:%M"),
                "content": build_completion_message(state),
                "artifactIds": [artifact["id"] for artifact in artifacts],
                "citations": citations,
            },
        }
    )
    emit(
        {
            "type": "run.completed",
            "runName": state.get("run_name", ""),
            "workflowEngine": state.get("workflow_engine", "unknown"),
            "llmMode": state.get("llm_mode", "unknown"),
            "reportPath": state.get("report_path", ""),
            "mindmapPath": state.get("mindmap_path", ""),
            "runLogPath": state.get("run_log_path", ""),
            "warnings": state.get("warnings", []),
            "paperCount": len(state.get("papers", [])),
            "supportingCount": len(state.get("supporting_papers", [])),
            "rejectedCount": len(state.get("rejected_papers", [])),
        }
    )


def build_artifacts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    run_name = state.get("run_name", timestamp_name())
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return [
        markdown_artifact(
            "survey",
            "Survey",
            "调研报告",
            state.get("report_path", ""),
            run_name,
            created_at,
        ),
        markdown_artifact(
            "mindmap",
            "Mindmap",
            "思维导图",
            state.get("mindmap_path", ""),
            run_name,
            created_at,
        ),
        matrix_artifact(state, run_name, created_at),
        code_artifact(state, run_name, created_at),
    ]


def markdown_artifact(
    artifact_id: str,
    title: str,
    summary: str,
    path: str,
    run_name: str,
    created_at: str,
) -> Dict[str, Any]:
    content = read_text(path)
    return {
        "id": artifact_id,
        "title": title,
        "kind": "markdown",
        "versions": [
            {
                "id": run_name,
                "label": run_name,
                "createdAt": created_at,
                "summary": summary,
                "content": content,
            }
        ],
    }


def matrix_artifact(
    state: Dict[str, Any], run_name: str, created_at: str
) -> Dict[str, Any]:
    core_rows = [
        {
            "id": f"paper-{index + 1}",
            "title": item.get("title", ""),
            "year": str(item.get("year", "")),
            "source": item.get("source", ""),
            "importance": item.get("importance", "core"),
            "score": item.get("relevance_score", 0),
            "direction": item.get("category", ""),
            "method": item.get("method", ""),
            "evidence": item.get("contribution", ""),
            "confidence": confidence_from_score(item.get("relevance_score", 0)),
        }
        for index, item in enumerate(state.get("paper_analyses", []))
    ]
    supporting_rows = [
        {
            "id": f"supporting-{index + 1}",
            "title": item.get("title", ""),
            "year": str(item.get("year", "")),
            "source": item.get("source", ""),
            "importance": item.get("importance", "supporting"),
            "score": item.get("relevance_score", 0),
            "direction": "补充候选",
            "method": "Lower-weight candidate retained for broader coverage.",
            "evidence": item.get("summary", ""),
            "confidence": confidence_from_score(item.get("relevance_score", 0)),
        }
        for index, item in enumerate(state.get("supporting_papers", []))
    ]
    return {
        "id": "matrix",
        "title": "Literature Matrix",
        "kind": "literature-matrix",
        "versions": [
            {
                "id": run_name,
                "label": run_name,
                "createdAt": created_at,
                "summary": "代表论文矩阵",
                "content": "",
                "literature": core_rows + supporting_rows,
            }
        ],
    }


def code_artifact(
    state: Dict[str, Any], run_name: str, created_at: str
) -> Dict[str, Any]:
    log_path = state.get("run_log_path", "")
    content = read_text(log_path)
    return {
        "id": "run-log",
        "title": "Run Log",
        "kind": "code",
        "versions": [
            {
                "id": run_name,
                "label": run_name,
                "createdAt": created_at,
                "summary": "workflow run_log.json",
                "content": content,
                "language": "json",
            }
        ],
    }


def build_completion_message(state: Dict[str, Any]) -> str:
    warnings = state.get("warnings", [])
    warning_text = ""
    if warnings:
        warning_text = "\n\n注意：本次运行记录了 warning，可在 Run Log 中查看。"
    return (
        f"已完成《{state.get('topic', 'research topic')}》的多 Agent 科研协作流程。\n\n"
        f"- 工作流：{state.get('workflow_engine', 'unknown')}\n"
        f"- 模型模式：{state.get('llm_mode', 'unknown')}\n"
        f"- 正文论文：{len(state.get('papers', []))} 篇\n"
        f"- 补充候选：{len(state.get('supporting_papers', []))} 篇\n"
        f"- 过滤候选：{len(state.get('rejected_papers', []))} 篇\n\n"
        "右侧 Artifacts 已更新调研报告、思维导图、文献矩阵和运行日志。"
        f"{warning_text}"
    )


def initial_agent_events() -> Iterable[Dict[str, Any]]:
    agents = ["planner", "scholar", "reader", "critic", "writer"]
    for index, agent_id in enumerate(agents):
        yield {
            "type": "agent.status",
            "agentId": agent_id,
            "status": "queued" if index else "working",
            "currentTask": "Waiting for workflow handoff",
            "progress": 0,
            "timestamp": now(),
        }


def normalize_provider(provider: str) -> str:
    if provider == "qwen":
        return "dashscope"
    if provider in {"auto", "deepseek", "dashscope", "mock"}:
        return provider
    return "auto"


def normalize_mock_mode(provider: str, mock_mode: str) -> str:
    if provider == "mock":
        return "always"
    if provider in {"deepseek", "dashscope"}:
        return "never"
    if mock_mode in {"auto", "always", "never"}:
        return mock_mode
    return "auto"


def confidence_from_score(score: Any) -> str:
    value = to_float(score, 0.0)
    if value >= 6:
        return "high"
    if value >= 3:
        return "medium"
    return "low"


def to_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def read_text(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def emit(event: Dict[str, Any]) -> None:
    event.setdefault("timestamp", now())
    print(json.dumps(event, ensure_ascii=True), flush=True)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp_name() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sanitize_run_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or timestamp_name()


def sanitize_error(message: str) -> str:
    return re.sub(r"(sk-|ds-)[A-Za-z0-9_-]+", "[redacted]", message)


def scrub_surrogates(value: Any) -> Any:
    if isinstance(value, str):
        return value.encode("utf-8", "replace").decode("utf-8")
    if isinstance(value, list):
        return [scrub_surrogates(item) for item in value]
    if isinstance(value, dict):
        return {key: scrub_surrogates(item) for key, item in value.items()}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
