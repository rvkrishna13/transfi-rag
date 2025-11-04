#!/usr/bin/env python3
"""
CLI script for querying the RAG system.
"""
import json
import time
import asyncio
import logging
import warnings
from typing import List, Optional, Dict, Any

import click

from core.query_engine import get_query_engine, QueryMetrics
from core.utils import format_sources, format_metrics, aggregate_metrics, print_query_result_block

# Suppress all warnings in terminal output
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*importlib.metadata.*")
warnings.filterwarnings("ignore", message=".*packages_distributions.*")

# Basic logging configuration (concise, info-level)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_questions_from_file(path: str) -> List[str]:
    """Load questions from file (JSON list or newline-separated)."""
    with open(path, "r") as f:
        content = f.read().strip()
    try:
        # If the file is JSON, support ["q1", "q2"]
        loaded = json.loads(content)
        if isinstance(loaded, list):
            return [str(x) for x in loaded]
    except Exception:
        pass
    # Fallback: newline-separated
    return [line.strip() for line in content.splitlines() if line.strip()]


@click.command()
@click.option("--question", type=str, default=None, help="Single question to ask.")
@click.option("--questions", type=str, default=None, help="Path to file with questions (newline or JSON list).")
@click.option("--concurrent", is_flag=True, default=False, show_default=True, help="Process multiple questions concurrently.")
def main(question: Optional[str], questions: Optional[str], concurrent: bool) -> None:
    """
    Run queries against the RAG system and print answers with citations and metrics.

    Examples:
        python query.py --question "What is BizPay and its key features?"
        python query.py --questions questions.txt
        python query.py --questions questions.txt --concurrent
    """
    question_list: List[str] = []
    if question:
        question_list.append(question)
    if questions:
        question_list.extend(load_questions_from_file(questions))
    question_list = [q for q in question_list if q and q.strip()]

    if not question_list:
        raise click.UsageError("Provide either --question or --questions with questions.")

    # Get singleton query engine instance (module-level)
    engine = get_query_engine()
    
    batch_start = time.time()
    results = asyncio.run(engine.run_queries(question_list, concurrent=concurrent))
    batch_total = time.time() - batch_start

    multi = len(question_list) > 1
    for idx, res in enumerate(results):
        is_last = idx == len(results) - 1
        print_query_result_block(res, include_metrics=not multi, include_separator=not is_last or multi)

    if multi:
        print("\n" + ("-" * 80) + "\n")
        total = aggregate_metrics(results, total_latency_s=batch_total)
        print(format_metrics(total))
        print("\n" + ("-" * 80) + "\n")


if __name__ == "__main__":
    main()
