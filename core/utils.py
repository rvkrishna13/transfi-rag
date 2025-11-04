"""
Utility functions for formatting and aggregating query results.
Shared by both CLI and API interfaces.
"""
from typing import List, Dict, Any
from core.query_engine import QueryMetrics


def format_sources(citations: List[Dict[str, Any]]) -> str:
    """Format citations for display."""
    lines = ["Sources:"]
    for idx, c in enumerate(citations, start=1):
        url = c.get("url", "")
        title = c.get("title", "")
        snippet = c.get("snippet", "").strip().replace("\n", " ")
        lines.append(f"  URL:{url}\n     Snippet: \"{snippet}\"")
    return "\n".join(lines)


def format_metrics(metrics: QueryMetrics) -> str:
    """Format metrics for display."""
    return "\n".join(
        [
            "Metrics:",
            f"  Total Latency: {metrics.total_latency_s:.2f}s",
            f"  Retrieval Time: {metrics.retrieval_time_s:.2f}s",
            f"  LLM Time: {metrics.llm_time_s:.2f}s",
            f"  Post-processing Time: {metrics.post_time_s:.2f}s",
            f"  Documents Retrieved: {metrics.docs_retrieved}",
            f"  Documents Used in Answer: {metrics.docs_used}",
            f"  Input Tokens: {metrics.input_tokens}",
            f"  Output Tokens: {metrics.output_tokens}",
            f"  Estimated Cost: ${metrics.estimated_cost_usd:.4f}",
        ]
    )


def aggregate_metrics(results: List[Dict[str, Any]], total_latency_s: float) -> QueryMetrics:
    """Aggregate metrics across multiple queries."""
    retrieval_sum = 0.0
    llm_sum = 0.0
    post_sum = 0.0
    docs_retrieved = 0
    docs_used = 0
    input_tokens = 0
    output_tokens = 0
    cost = 0.0
    for r in results:
        m: QueryMetrics = r["metrics"]
        retrieval_sum += m.retrieval_time_s
        llm_sum += m.llm_time_s
        post_sum += m.post_time_s
        docs_retrieved += m.docs_retrieved
        docs_used += m.docs_used
        input_tokens += m.input_tokens
        output_tokens += m.output_tokens
        cost += m.estimated_cost_usd
    return QueryMetrics(
        total_latency_s=round(total_latency_s, 2),
        retrieval_time_s=round(retrieval_sum, 2),
        llm_time_s=round(llm_sum, 2),
        post_time_s=round(post_sum, 2),
        docs_retrieved=docs_retrieved,
        docs_used=docs_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=cost,  # Keep cost at 4 decimal places
    )


def format_ingestion_metrics(metrics: Dict[str, Any]) -> str:
    """Format ingestion metrics for display."""
    errors = metrics.get("errors", [])
    errors_str = ", ".join([e.get("message", str(e)) for e in errors]) if errors else "None"
    
    return "\n".join([
        "=== Ingestion Metrics ===",
        "",
        f"Total Time: {metrics.get('total_time_seconds', 0):.1f}s",
        f"Pages Scraped: {metrics.get('pages_scraped', 0)}",
        f"Pages Failed: {metrics.get('pages_failed', 0)}",
        f"Total Chunks Created: {metrics.get('total_chunks_created', 0)}",
        f"Total Tokens Processed: {metrics.get('total_tokens_processed', 0):,}",
        f"Embedding Generation Time: {metrics.get('embedding_generation_time_seconds', 0):.1f}s",
        f"Indexing Time: {metrics.get('indexing_time_seconds', 0):.1f}s",
        f"Average Scraping Time per Page: {metrics.get('average_scraping_time_per_page_seconds', 0):.1f}s",
        f"Errors: {errors_str}",
    ])


def format_citations_for_api(citations: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Format citations for API response (removes title, keeps url and snippet)."""
    return [
        {
            "url": c.get("url", ""),
            "snippet": c.get("snippet", "")
        }
        for c in citations
    ]

def print_query_result_block(result: Dict[str, Any], include_metrics: bool = True, include_separator: bool = True) -> None:
    """Print a single query result block."""
    question = result["question"]
    answer = result["answer"].strip()
    citations = result["citations"]
    metrics: QueryMetrics = result["metrics"]

    print(f"Question: {question}")
    print(f"\nAnswer: {answer}\n")
    print(format_sources(citations))
    print("")
    if include_metrics:
        print(format_metrics(metrics))
    if include_separator:
        print("\n" + ("-" * 80) + "\n")