from __future__ import annotations

import argparse
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
        help="Maximum number of papers to retrieve from arXiv.",
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
        default="outputs",
        help="Directory for survey.md, mindmap.md, and run_log.json.",
    )
    parser.add_argument(
        "--memory-path",
        default="data/long_term_memory.json",
        help="JSON file used as long-term memory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = run_research_workflow(
        topic=args.topic,
        max_papers=args.max_papers,
        pdf_paths=[Path(p) for p in args.pdf],
        output_dir=Path(args.output_dir),
        memory_path=Path(args.memory_path),
        mock_mode=args.mock,
        provider=args.provider,
    )

    print("\n=== AI Research Agent Team finished ===")
    print(f"Topic: {state['topic']}")
    print(f"Workflow: {state.get('workflow_engine', 'unknown')}")
    print(f"LLM mode: {state.get('llm_mode', 'unknown')}")
    print(f"Survey: {state.get('report_path')}")
    print(f"Mindmap: {state.get('mindmap_path')}")
    print(f"Run log: {state.get('run_log_path')}")
    if state.get("warnings"):
        print("\nWarnings:")
        for warning in state["warnings"]:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
