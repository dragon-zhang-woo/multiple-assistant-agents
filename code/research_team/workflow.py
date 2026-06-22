from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

from research_team.agents import (
    CriticAgent,
    ManagerAgent,
    ReadingAgent,
    SearchAgent,
    WriterAgent,
    add_message,
)
from research_team.llm import build_llm
from research_team.memory import LongTermMemory, ProceduralMemory, SemanticMemory
from research_team.models import ResearchState

EventSink = Callable[[Dict[str, Any]], None]

NODE_AGENT_MAP = {
    "manager": ("planner", "Planner", 18),
    "memory_retrieve": ("planner", "Memory", 28),
    "search": ("scholar", "Scholar", 44),
    "read": ("reader", "Reader", 62),
    "critique": ("critic", "Critic", 78),
    "write": ("writer", "Writer", 92),
    "memory_update": ("writer", "Memory", 100),
}


def run_research_workflow(
    topic: str,
    max_papers: int,
    candidate_pool: int,
    min_relevance: float,
    sort_by: str,
    pdf_paths: List[Path],
    output_dir: Path,
    memory_path: Path,
    mock_mode: str = "auto",
    provider: str = "auto",
    run_name: str = "",
    latest_dir: Path | None = None,
    event_sink: EventSink | None = None,
) -> ResearchState:
    llm, llm_warnings = build_llm(mock_mode, provider)
    state: ResearchState = {
        "topic": topic,
        "max_papers": max_papers,
        "candidate_pool": candidate_pool,
        "min_relevance": min_relevance,
        "sort_by": sort_by,
        "pdf_paths": [str(path) for path in pdf_paths],
        "output_dir": str(output_dir),
        "memory_path": str(memory_path),
        "run_name": run_name,
        "latest_dir": str(latest_dir) if latest_dir else "",
        "messages": [],
        "tool_logs": [],
        "warnings": llm_warnings,
        "retrieved_memories": [],
        "papers": [],
        "supporting_papers": [],
        "rejected_papers": [],
        "search_queries": [],
        "search_diagnostics": {},
        "paper_analyses": [],
        "pdf_notes": [],
        "llm_mode": llm.mode,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    add_message(state, "System", "Start Research Agent Team workflow.")

    memory = LongTermMemory(memory_path)
    semantic_memory_path = memory_path.parent / (memory_path.stem + "_semantic.json")
    procedural_memory_path = memory_path.parent / (memory_path.stem + "_procedural.json")
    semantic_memory = SemanticMemory(semantic_memory_path)
    procedural_memory = ProceduralMemory(procedural_memory_path)
    state["semantic_memory_path"] = str(semantic_memory_path)
    state["procedural_memory_path"] = str(procedural_memory_path)
    agents = {
        "manager": ManagerAgent(),
        "search": SearchAgent(),
        "read": ReadingAgent(),
        "critique": CriticAgent(),
        "write": WriterAgent(),
    }

    def manager_node(current: ResearchState) -> ResearchState:
        return agents["manager"].run(current, llm)

    def memory_retrieve_node(current: ResearchState) -> ResearchState:
        retrieved = memory.retrieve(current["topic"])
        current["retrieved_memories"] = retrieved
        # Pull semantic + procedural memory using the domain inferred earlier.
        domain = (current.get("topic_profile") or {}).get("domain") or "general"
        try:
            current["semantic_memory"] = semantic_memory.retrieve(domain)
        except Exception:
            current["semantic_memory"] = {}
        try:
            current["procedural_memory"] = procedural_memory.retrieve(domain)
        except Exception:
            current["procedural_memory"] = {}
        current.setdefault("tool_logs", []).append(
            {
                "tool": "memory_retrieve",
                "memory_count": len(retrieved),
                "semantic_directions": len(
                    (current["semantic_memory"] or {}).get("directions", []) or []
                ),
                "procedural_queries": len(
                    (current["procedural_memory"] or {}).get("effective_queries", []) or []
                ),
            }
        )
        add_message(
            current,
            "Memory",
            f"Retrieved {len(retrieved)} episodic + "
            f"{len((current['semantic_memory'] or {}).get('directions', []) or [])} semantic + "
            f"{len((current['procedural_memory'] or {}).get('effective_queries', []) or [])} procedural memory entries.",
        )
        return current

    def search_node(current: ResearchState) -> ResearchState:
        before_paper_count = len(current.get("papers", []))
        current = agents["search"].run(current, llm)
        # Procedural memory bookkeeping: which queries did we run, did we get hits?
        domain = (current.get("topic_profile") or {}).get("domain") or "general"
        queries = current.get("search_queries", []) or []
        paper_count_after = len(current.get("papers", []))
        try:
            procedural_memory.record_search(
                domain=domain,
                queries=queries,
                paper_count=max(paper_count_after, paper_count_after - before_paper_count),
            )
        except Exception:
            pass
        return current

    def read_node(current: ResearchState) -> ResearchState:
        return agents["read"].run(current, llm)

    def critique_node(current: ResearchState) -> ResearchState:
        return agents["critique"].run(current, llm)

    def write_node(current: ResearchState) -> ResearchState:
        return agents["write"].run(current, llm)

    def memory_update_node(current: ResearchState) -> ResearchState:
        memory.add_run(
            topic=current["topic"],
            papers=current.get("papers", []),
            analyses=current.get("paper_analyses", []),
            report_path=current.get("report_path", ""),
        )
        # Distill semantic memory from this run's analyses + critique.
        domain = (current.get("topic_profile") or {}).get("domain") or "general"
        try:
            semantic_memory.update_from_run(
                domain=domain,
                topic_profile=current.get("topic_profile") or {},
                analyses=current.get("paper_analyses", []) or [],
                critique=current.get("critique_summary", "") or "",
            )
        except Exception:
            pass
        current.setdefault("tool_logs", []).append(
            {
                "tool": "memory_update",
                "memory_path": str(memory_path),
                "semantic_memory_path": str(semantic_memory_path),
                "procedural_memory_path": str(procedural_memory_path),
            }
        )
        add_message(
            current,
            "Memory",
            "Updated episodic + semantic + procedural memory.",
        )
        return current

    nodes = [
        ("manager", manager_node),
        ("memory_retrieve", memory_retrieve_node),
        ("search", search_node),
        ("read", read_node),
        ("critique", critique_node),
        ("write", write_node),
        ("memory_update", memory_update_node),
    ]

    emit_event(
        event_sink,
        {
            "type": "trace.append",
            "agentId": "planner",
            "title": "Run started",
            "detail": f"Research topic: {topic}",
        },
    )
    state = run_with_langgraph_if_available(
        state, instrument_nodes(nodes, event_sink), max_critic_retries=1
    )
    state["completed_at"] = datetime.now().isoformat(timespec="seconds")
    write_run_log(state)
    if latest_dir:
        publish_latest(Path(state["output_dir"]), latest_dir)
    return state


def instrument_nodes(
    nodes: List[tuple[str, Callable[[ResearchState], ResearchState]]],
    event_sink: EventSink | None,
) -> List[tuple[str, Callable[[ResearchState], ResearchState]]]:
    if event_sink is None:
        return nodes

    wrapped = []
    for name, node in nodes:
        agent_id, label, progress = NODE_AGENT_MAP.get(name, ("planner", name, 0))

        def wrapped_node(
            current: ResearchState,
            node_name: str = name,
            node_func: Callable[[ResearchState], ResearchState] = node,
            current_agent_id: str = agent_id,
            current_label: str = label,
            current_progress: int = progress,
        ) -> ResearchState:
            emit_event(
                event_sink,
                {
                    "type": "agent.status",
                    "agentId": current_agent_id,
                    "status": "working",
                    "currentTask": f"{current_label} is running {node_name}",
                    "progress": max(current_progress - 12, 4),
                },
            )
            emit_event(
                event_sink,
                {
                    "type": "trace.append",
                    "agentId": current_agent_id,
                    "title": f"{current_label} started",
                    "detail": f"Executing workflow node: {node_name}",
                },
            )
            next_state = node_func(current)
            emit_event(
                event_sink,
                {
                    "type": "agent.status",
                    "agentId": current_agent_id,
                    "status": "done",
                    "currentTask": f"{current_label} finished {node_name}",
                    "progress": current_progress,
                },
            )
            emit_event(
                event_sink,
                {
                    "type": "trace.append",
                    "agentId": current_agent_id,
                    "title": f"{current_label} completed",
                    "detail": summarize_node_result(node_name, next_state),
                },
            )
            return next_state

        wrapped.append((name, wrapped_node))
    return wrapped


def emit_event(event_sink: EventSink | None, event: Dict[str, Any]) -> None:
    if event_sink is None:
        return
    event.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    event_sink(event)


def summarize_node_result(node_name: str, state: ResearchState) -> str:
    if node_name == "manager":
        return "Planning is ready."
    if node_name == "memory_retrieve":
        return f"Retrieved {len(state.get('retrieved_memories', []))} memory entries."
    if node_name == "search":
        return (
            f"Accepted {len(state.get('papers', []))} core papers, kept "
            f"{len(state.get('supporting_papers', []))} supporting papers, and rejected "
            f"{len(state.get('rejected_papers', []))} candidates."
        )
    if node_name == "read":
        return (
            f"Produced {len(state.get('paper_analyses', []))} paper analyses and "
            f"{len(state.get('pdf_notes', []))} PDF notes."
        )
    if node_name == "critique":
        return "Reflection summary is ready."
    if node_name == "write":
        return f"Wrote report artifacts to {state.get('output_dir', '')}."
    if node_name == "memory_update":
        return f"Updated long-term memory at {state.get('memory_path', '')}."
    return "Node completed."


def run_with_langgraph_if_available(
    state: ResearchState,
    nodes: List[tuple[str, Callable[[ResearchState], ResearchState]]],
    max_critic_retries: int = 1,
) -> ResearchState:
    node_map = {name: func for name, func in nodes}

    def should_retry(current: ResearchState) -> str:
        decision = current.get("critic_decision") or {}
        retries_used = int(current.get("critic_retries_done", 0))
        if (
            decision.get("needs_more_search")
            and retries_used < max_critic_retries
        ):
            current["critic_retries_done"] = retries_used + 1
            return "retry"
        return "advance"

    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        state.setdefault("warnings", []).append(
            "LangGraph is not installed; executed the same workflow sequentially."
        )
        state["workflow_engine"] = "sequential-fallback"
        return _run_sequential_with_retry(state, nodes, max_critic_retries, should_retry)

    try:
        graph = StateGraph(ResearchState)
        for name, node in nodes:
            graph.add_node(name, node)
        # Linear edges, except critique which is conditional.
        for (name, _), (next_name, _) in zip(nodes, nodes[1:]):
            if name == "critique":
                continue
            graph.add_edge(name, next_name)
        graph.add_conditional_edges(
            "critique",
            should_retry,
            {"retry": "search", "advance": "write"},
        )
        graph.add_edge(nodes[-1][0], END)
        graph.set_entry_point(nodes[0][0])
        compile_kwargs: Dict[str, Any] = {}
        checkpointer = _build_checkpointer(state)
        if checkpointer is not None:
            compile_kwargs["checkpointer"] = checkpointer
            state["checkpointer"] = "sqlite"
        app = graph.compile(**compile_kwargs)
        state["workflow_engine"] = "langgraph"
        invoke_kwargs: Dict[str, Any] = {}
        if checkpointer is not None:
            invoke_kwargs["config"] = {
                "configurable": {
                    "thread_id": state.get("run_name") or "default",
                }
            }
        final_state = app.invoke(state, **invoke_kwargs) if invoke_kwargs else app.invoke(state)
        final_state["workflow_engine"] = "langgraph"
        return final_state
    except Exception as exc:
        state.setdefault("warnings", []).append(
            f"LangGraph execution failed ({exc}); executed sequential fallback."
        )
        state["workflow_engine"] = "sequential-fallback"
        return _run_sequential_with_retry(state, nodes, max_critic_retries, should_retry)


def _run_sequential_with_retry(
    state: ResearchState,
    nodes: List[tuple[str, Callable[[ResearchState], ResearchState]]],
    max_critic_retries: int,
    should_retry: Callable[[ResearchState], str],
) -> ResearchState:
    """Sequential fallback that also honors the Reflexion retry edge."""
    pre_critique: List[tuple[str, Callable[[ResearchState], ResearchState]]] = []
    post_critique: List[tuple[str, Callable[[ResearchState], ResearchState]]] = []
    critique_node = None
    seen_critique = False
    for name, func in nodes:
        if name == "critique":
            critique_node = func
            seen_critique = True
            continue
        if not seen_critique:
            pre_critique.append((name, func))
        else:
            post_critique.append((name, func))

    for _, func in pre_critique:
        state = func(state)

    if critique_node is None:
        for _, func in post_critique:
            state = func(state)
        return state

    while True:
        state = critique_node(state)
        action = should_retry(state)
        if action != "retry":
            break
        # Replay search → read before re-running critique.
        for name, func in pre_critique:
            if name in {"search", "read"}:
                state = func(state)

    for _, func in post_critique:
        state = func(state)
    return state


def write_run_log(state: ResearchState) -> None:
    output_dir = Path(state.get("output_dir", "outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "run_log.json"
    state["run_log_path"] = str(log_path)
    log_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def publish_latest(output_dir: Path, latest_dir: Path) -> None:
    latest_dir.parent.mkdir(parents=True, exist_ok=True)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(output_dir, latest_dir)


def _build_checkpointer(state: ResearchState):
    """Best-effort SqliteSaver instantiation. Returns ``None`` when the
    optional dependency is missing so callers can degrade gracefully."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except Exception:
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except Exception:
            return None
    try:
        output_dir = Path(state.get("output_dir") or "outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        db_path = output_dir / "checkpoints.sqlite"
        return SqliteSaver.from_conn_string(str(db_path))
    except Exception:
        try:
            from langgraph.checkpoint.memory import MemorySaver

            return MemorySaver()
        except Exception:
            return None
