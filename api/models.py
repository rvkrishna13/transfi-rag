from typing import List, Optional, Union
from pydantic import BaseModel, HttpUrl, Field, validator
from datetime import datetime

# Import QueryMetrics from core (defined as Pydantic model there)
from core.query_engine import QueryMetrics


class IngestRequest(BaseModel):
    urls: List[str] = Field(..., description="Website URLs to ingest")
    callback_url: HttpUrl = Field(..., description="Optional webhook URL for async notifications")
    

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="Question to ask")


class Citation(BaseModel):
    url: str
    snippet: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
    metrics: QueryMetrics


class BatchQueryRequest(BaseModel):
    questions: List[str] = Field(..., min_items=1, max_items=50)
    callback_url: Optional[HttpUrl] = Field(None, description="Optional webhook URL for async notifications")


class BatchQueryResponse(BaseModel):
    results: List[QueryResponse]
    metrics: QueryMetrics
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[dict] = None


# Webhook payload models based on type
class IngestionWebhookPayload(BaseModel):
    """Webhook payload for ingestion operations."""
    type: str = "ingestion"
    status: str  # "success" or "failed"
    job_id: str
    urls: List[str]
    metrics: Optional[List[dict]] = None
    error: Optional[str] = None


class BatchQueryWebhookPayload(BaseModel):
    """Webhook payload for batch query operations."""
    type: str = "batch_query"
    status: str = "success"
    results: List[dict]
    metrics: dict

class WebhookRequest(BaseModel):
    type: str
    payload: Union[IngestionWebhookPayload, BatchQueryWebhookPayload]