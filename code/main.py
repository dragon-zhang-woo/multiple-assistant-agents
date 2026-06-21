from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from research_team.workflow import run_research_workflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Research Agent Team: multi-agent survey assistant."
    )
    parser.add_argument(
        "--topic",
        default="近年来Agent Memory有哪些研究方向？",
        help="Research question or survey topic.",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=5,
        help="Maximum number of core papers to keep in the report.",
    )
    parser.add_argument(
        "--candidate-pool",
        type=int,
        default=25,
        help="Number of search candidates to inspect before relevance filtering. Use 0 for offline fallback samples.",
    )
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=3.0,
        help="Minimum relevance score required for a paper to enter the report.",
    )
    parser.add_argument(
        "--sort",
        choices=["relevance", "submittedDate"],
        default="relevance",
        help="Search sort mode before local relevance filtering.",
    )
    parser.add_argument(
        "--pdf",
        action="append",
        default=[],
        help="Optional local PDF path. Can be passed multiple times.",
    )
    parser.add_argument(
        "--mock",
        choices=["auto", "always", "never"],
        default="auto",
        help="auto uses DashScope when configured, otherwise deterministic mock.",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "dashscope", "deepseek"],
        default="auto",
        help="LLM provider for real API mode. auto prefers DeepSeek when DEEPSEEK_API_KEY is set, then DashScope.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for survey.md, mindmap.md, and run_log.json. Defaults to runs/<timestamp>.",
    )
    parser.add_argument(
        "--memory-path",
        default="memory/long_term_memory.json",
        help="JSON file used as long-term memory.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Stable name for this run directory. Defaults to timestamp.",
    )
    parser.add_argument(
        "--dry-run-config",
        action="store_true",
        help="Print resolved configuration without running agents or writing files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_name = sanitize_run_name(args.run_name) if args.run_name else timestamp_name()
    output_dir = Path(args.output_dir) if args.output_dir else Path("runs") / run_name
    config = {
        "topic": args.topic,
        "max_papers": args.max_papers,
        "candidate_pool": args.candidate_pool,
        "min_relevance": args.min_relevance,
        "sort": args.sort,
        "mock": args.mock,
        "provider": args.provider,
        "output_dir": str(output_dir),
        "memory_path": args.memory_path,
        "run_name": run_name,
    }
    if args.dry_run_config:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return

    state = run_research_workflow(
        topic=args.topic,
        max_papers=args.max_papers,
        candidate_pool=args.candidate_pool,
        min_relevance=args.min_relevance,
        sort_by=args.sort,
        pdf_paths=[Path(p) for p in args.pdf],
        output_dir=output_dir,
        memory_path=Path(args.memory_path),
        mock_mode=args.mock,
        provider=args.provider,
        run_name=run_name,
        latest_dir=Path("outputs") / "latest",
    )

    print("\n=== AI Research Agent Team finished ===")
    print(f"Topic: {state['topic']}")
    print(f"Workflow: {state.get('workflow_engine', 'unknown')}")
    print(f"LLM mode: {state.get('llm_mode', 'unknown')}")
    print(f"Survey: {state.get('report_path')}")
    print(f"Mindmap: {state.get('mindmap_path')}")
    print(f"Run log: {state.get('run_log_path')}")
    print(f"Latest copy: {state.get('latest_dir')}")
    if state.get("warnings"):
        print("\nWarnings:")
        for warning in state["warnings"]:
            print(f"- {warning}")


def timestamp_name() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sanitize_run_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or timestamp_name()


if __name__ == "__main__":
    main()
