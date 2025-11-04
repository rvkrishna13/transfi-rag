"""
Service Layer: Business logic and orchestration.
Reuses core functionality from core/ without duplication.
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

import httpx

from api.models import (
    IngestRequest, QueryRequest, QueryResponse, QueryMetrics,
    BatchQueryRequest, BatchQueryResponse, ErrorResponse, WebhookRequest
)

from core.ingestion_pipeline import DataIngestionPipeline
from core.query_engine import get_query_engine
from core.utils import aggregate_metrics, format_citations_for_api, format_metrics, print_query_result_block

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 30
WEBHOOK_MAX_RETRIES = 3
WEBHOOK_RETRY_DELAY = 5


async def send_webhook_with_retry(
    callback_url: str,
    payload: dict,
    type: str,
    max_retries: int = WEBHOOK_MAX_RETRIES
) -> tuple[bool, Optional[dict], Optional[str]]:
    """
    Send webhook with retry logic and comprehensive logging.
    Stateless and thread-safe.
    
    Returns:
        (success: bool, response_data: Optional[dict], error_message: Optional[str])
    """
    attempt = 0
    last_error = None
    
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
        while attempt < max_retries:
            attempt += 1
            timestamp = datetime.now()
            
            try:
                logger.info(
                    "Webhook attempt %d/%d to %s at %s",
                    attempt, max_retries, callback_url, timestamp.isoformat()
                )
                    
                response = await client.post(callback_url, json={"type": type, "payload": payload})
                response.raise_for_status()
                
                response_data = response.json() if response.content else {}
                
                logger.info(
                    "Webhook SUCCESS: %s responded with status %d at %s",
                    callback_url, response.status_code, datetime.now().isoformat()
                )
                
                return True, response_data, None
                
            except httpx.TimeoutException:
                last_error = f"Timeout after {WEBHOOK_TIMEOUT}s"
                logger.warning(
                    "Webhook TIMEOUT (attempt %d/%d): %s - %s",
                    attempt, max_retries, callback_url, last_error
                )
                
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                logger.warning(
                    "Webhook HTTP ERROR (attempt %d/%d): %s - %s",
                    attempt, max_retries, callback_url, last_error
                )
                if 400 <= e.response.status_code < 500:
                    break
            
            except httpx.ConnectError as e:
                last_error = f"Connection failed: {str(e)}"
                logger.warning(
                    "Webhook CONNECTION ERROR (attempt %d/%d): %s - %s",
                    attempt, max_retries, callback_url, last_error
                )
                    
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(
                    "Webhook ERROR (attempt %d/%d): %s - %s",
                    attempt, max_retries, callback_url, last_error,
                    exc_info=True
                )
            
            if attempt < max_retries:
                await asyncio.sleep(WEBHOOK_RETRY_DELAY * attempt)
        
        logger.error(
            "Webhook FAILED after %d attempts to %s: %s",
            max_retries, callback_url, last_error
        )
        return False, None, last_error


async def start_ingestion(request: IngestRequest) -> dict:
    """
    Service layer: Orchestrate ingestion using core DataIngestionPipeline.
    Returns immediately with job ID, processes asynchronously.
    Stateless and thread-safe.
    """
    job_id = str(uuid.uuid4())
    
    async def ingest_and_webhook():
        try:
            pipeline = DataIngestionPipeline(clear_collection=True)
            scraping_metrics = []
            for url in request.urls:
                logger.info("Starting ingestion job %s for URL: %s", job_id, url)
                start_time = time.time()
                result = await pipeline.run(
                    url=url,
                    page_types=["products", "solutions"],
                )
                metrics = result.get("metrics", {})
                metrics["job_id"] = job_id
                metrics["processing_time_s"] = time.time() - start_time
                scraping_metrics.append(metrics)
            
            try:
                payload = {
                    "status": "success",
                    "job_id": job_id,
                    "urls": request.urls,
                    "metrics": scraping_metrics,
                    "timestamp": datetime.now().isoformat()
                }
                success, _, error = await send_webhook_with_retry(
                    str(request.callback_url), payload, "ingestion"
                )
                if not success:
                    logger.warning(
                        "Webhook delivery failed but ingestion succeeded. Error: %s. Callback URL: %s",
                        error, request.callback_url
                    )
            except Exception as webhook_exc:
                logger.error(
                    "Exception while sending success webhook for job %s: %s. Callback URL: %s",
                    job_id, str(webhook_exc), request.callback_url,
                    exc_info=True
                )
                
        except Exception as e:
            logger.error("Ingestion failed for %s: %s", request.url, str(e), exc_info=True)
            
            try:
                payload = {
                    "status": "failed",
                    "job_id": job_id,
                    "url": request.url,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                success, _, webhook_error = await send_webhook_with_retry(str(request.callback_url), payload, "ingestion")
                if not success:
                    logger.error(
                        "Failed to send failure webhook for job %s: %s",
                        job_id, webhook_error
                    )
            except Exception as webhook_exc:
                logger.error(
                    "Exception while sending failure webhook for job %s: %s",
                    job_id, str(webhook_exc),
                    exc_info=True
                )
    
    asyncio.create_task(ingest_and_webhook())
    
    return {
        "status": "accepted",
        "message": f"Ingestion started",
        "job_id": job_id,
        "callback_url": str(request.callback_url)
    }


async def process_query(request: QueryRequest) -> QueryResponse:
    """
    Service layer: Process a single query using core query functionality.
    Stateless and thread-safe.
    """
    try:
        engine = get_query_engine()
        result = await engine.answer_question(request.question)
        citations = format_citations_for_api(result["citations"])
        metrics = result["metrics"]
        
        return QueryResponse(
            question=result["question"],
            answer=result["answer"],
            citations=citations,
            metrics=metrics
        )
        
    except Exception as e:
        logger.error("Query processing failed: %s", str(e), exc_info=True)
        raise


async def process_batch_query(request: BatchQueryRequest) -> BatchQueryResponse:
    """
    Service layer: Process multiple queries using core query functionality.
    Stateless and thread-safe.
    """
    callback_url = request.callback_url
    start_time = time.time()
    
    async def run():
        try:
            engine = get_query_engine()
            results = await engine.run_queries(
                questions=request.questions,
                concurrent=False
            )
            
            query_responses = []
            for r in results:
                citations = format_citations_for_api(r["citations"])
                query_responses.append(QueryResponse(
                    question=r["question"],
                    answer=r["answer"],
                    citations=citations,
                    metrics=r["metrics"]
                ))
            
            total_time = time.time() - start_time
            results_dicts = [{"metrics": r.metrics} for r in query_responses]
            aggregated_metrics = aggregate_metrics(results_dicts, total_latency_s=total_time)
            
            response = BatchQueryResponse(
                results=query_responses,
                metrics=aggregated_metrics
            )
            
            if request.callback_url:
                try:
                    payload = {
                        "status": "success",
                        "results": [r.model_dump() for r in query_responses],
                        "metrics": aggregated_metrics.model_dump(),
                        "timestamp": datetime.now().isoformat()
                    }
                    success, _, error = await send_webhook_with_retry(
                        str(request.callback_url), payload, "batch_query"
                    )
                    if not success:
                        logger.warning(
                            "Webhook delivery failed but query succeeded. Error: %s. Callback URL: %s",
                            error, request.callback_url
                        )
                except Exception as webhook_exc:
                    logger.error(
                        "Exception while sending webhook: %s. Callback URL: %s",
                        str(webhook_exc), request.callback_url,
                        exc_info=True
                    )
            
            return response
        
        except Exception as e:
            logger.error("Batch query processing failed: %s", str(e), exc_info=True)
            raise
    
    if request.callback_url:
        asyncio.create_task(run())
        return {"message": "Answering questions started"}
    else:
        return await run()

def process_webhook(request: WebhookRequest):
    type = request.type
    now_ts = datetime.now().isoformat()
    print(f"[Webhook] Received at: {now_ts} | type={type}")

    if type == "ingestion":
        urls = request.payload.urls
        payload_ts = getattr(request.payload, 'timestamp', None)
        if payload_ts:
            print(f"[Webhook] Payload timestamp: {payload_ts}")

        metrics = request.payload.metrics

        for url, metric in zip(urls, metrics):
            print(f"Ingestion metrics for {url}:")
            print(metric)
            print("\n" + ("-" * 80) + "\n")
    elif type == "batch_query":
        results = request.payload.results
        metrics = request.payload.metrics
        payload_ts = getattr(request.payload, 'timestamp', None)
        if payload_ts:
            print(f"[Webhook] Payload timestamp: {payload_ts}")

        for idx, result in enumerate(results):
            is_last = idx == len(results) - 1
            print_query_result_block(result, include_metrics=False, include_separator=not is_last)
        if isinstance(metrics, dict):
            metrics_obj = QueryMetrics(**metrics)
        else:
            metrics_obj = metrics
        print(f"[Webhook] Aggregated metrics printed at: {datetime.now().isoformat()}")
        print(format_metrics(metrics_obj))
        print("\n" + ("-" * 80) + "\n")