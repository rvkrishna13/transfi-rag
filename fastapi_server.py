import logging
import warnings
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Suppress all warnings globally before imports
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*importlib.metadata.*")
warnings.filterwarnings("ignore", message=".*packages_distributions.*")

# Suppress importlib.metadata errors from third-party libraries
import importlib.metadata
if not hasattr(importlib.metadata, 'packages_distributions'):
    # Python 3.9 compatibility - add stub to prevent errors
    def _noop_packages_distributions():
        return {}
    importlib.metadata.packages_distributions = _noop_packages_distributions

from api.models import BatchQueryRequest, IngestRequest, QueryRequest
from api.services import process_batch_query, process_query, start_ingestion

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "RAG System is running"}

@app.post("/api/ingest")
async def ingest_data(request: IngestRequest):
    return await start_ingestion(request)

@app.post("/api/query")
async def query(request: QueryRequest):
    print(f"Query received: {request}")
    result = await process_query(request)
    return result

@app.post("/api/query/batch")
async def batch_query(request: BatchQueryRequest):
    result = await process_batch_query(request)
    return result

if __name__ == "__main__":
    uvicorn.run("fastapi_server:app", host="0.0.0.0", port=8000, reload=True)