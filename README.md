# TransFi RAG System

A Retrieval-Augmented Generation (RAG) system for answering questions about TransFi's products and solutions. The system scrapes website content, processes it, generates embeddings, and provides answers with cited sources.

## Features

- **Async-first architecture** for high performance
- **Web scraping** with depth-first traversal
- **Vector database** (ChromaDB) for efficient retrieval
- **LLM integration** (Google Gemini) for answer generation
- **RESTful API** with FastAPI
- **Webhook support** for async notifications
- **File-based querying** for batch processing
- **Comprehensive metrics** (latency, tokens, cost)

## Project Structure

```
transfi-rag/
├── core/                          # Core RAG components
│   ├── scraper.py                # Async web scraping with depth-first traversal
│   ├── text_processor.py         # HTML to text conversion and cleaning
│   ├── embeddings.py             # Sentence-transformers embedding generation
│   ├── vector_db.py              # ChromaDB vector database operations (singleton)
│   ├── llm_client.py             # Google Gemini LLM integration
│   ├── query_engine.py           # RAG query processing engine (singleton)
│   ├── ingestion_pipeline.py     # Complete ingestion pipeline (scrape → process → embed → store)
│   ├── utils.py                  # Shared utility functions (formatting, metrics)
│   └── document.py               # Document and metadata models (Pydantic)
├── api/                           # API layer
│   ├── models.py                 # Pydantic request/response models
│   └── services.py               # Business logic and webhook handling
├── data/                          # Data storage (gitignored)
│   ├── raw/                      # Raw HTML files (JSON format per page)
│   ├── cleaned/                  # Cleaned text files (.txt)
│   └── vector_db/                # ChromaDB persistent vector database
├── models/                        # Embedding models (gitignored)
│   └── all-MiniLM-L6-v2/         # Sentence-transformers model (auto-downloaded)
├── test/                          # Test files
│   └── questions.txt             # Sample questions for testing
├── tests/                         # Unit tests
│   ├── test_api.py              # API tests
│   └── test_core.py             # Core functionality tests
├── fastapi_server.py             # FastAPI application (port 8000)
├── webhook_receiver.py           # Webhook receiver server (port 8001)
├── ingest.py                     # CLI ingestion script
├── query.py                      # CLI query script
├── Makefile                      # Build automation commands
├── requirements.txt              # Python dependencies
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## Environment Setup

### Prerequisites

- **Python 3.9+** (tested with Python 3.9)
- **pip** (Python package manager)
- **Virtual environment** (recommended)

### Step-by-Step Installation

1. **Clone or download the project:**
   ```bash
   cd transfi-rag
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   make install
   ```
   
   Or manually:
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify installation:**
   ```bash
   make help
   python --version  # Should show Python 3.9+
   ```

### Configuration

#### LLM Configuration

The system uses **Google Gemini** for answer generation:
- Model: `gemini-2.5-flash` (default, configured in `core/query_engine.py`)
- API Key: Hardcoded in `core/llm_client.py` (set `GOOGLE_API_KEY` environment variable)

#### Embedding Model

- Model: `all-MiniLM-L6-v2` (Sentence Transformers)
- Automatically downloads on first use (~80MB)
- Location: `models/all-MiniLM-L6-v2/`

#### Vector Database

- Database: ChromaDB (Persistent)
- Location: `data/vector_db/`
- Collection: `transfi_rag`
- Distance metric: Cosine similarity

#### Query Configuration

- `TOP_K`: Number of chunks to retrieve (default: 10)
- `MODEL`: LLM model name (default: "gemini-2.5-flash")
- Configured in `core/query_engine.py` as class constants

#### Scraping Configuration

- `max_depth`: Maximum depth for depth-first scraping (default: 20, passed via CLI/API)
- `delay`: Delay between requests in seconds (default: 0.1)
- Note: No semaphore limit - uses aiohttp's connection pooling

## Installation Instructions

### Quick Start

```bash
# 1. Install dependencies
make install

# 2. Run ingestion (scrape and process data)
python ingest.py --url https://www.transfi.com

# 3. Query the system
python query.py --question "What is BizPay?"
```

### Detailed Installation

See [Environment Setup](#environment-setup) section above for complete installation steps.

## How to Run Both Scripts

### Script 1: Ingestion (`ingest.py`)

**Purpose:** Scrape website content, process it, generate embeddings, and store in vector database.

**Basic usage:**
```bash
python ingest.py --url https://www.transfi.com
```

**What it does:**
1. Scrapes the website (products and solutions pages)
2. Processes and cleans HTML content
3. Generates embeddings using Sentence Transformers
4. Stores in ChromaDB vector database
5. Saves raw HTML to `data/raw/` (JSON format)
6. Saves cleaned text to `data/cleaned/` (TXT format)

**Output:**
- Vector database populated in `data/vector_db/`
- Raw HTML files in `data/raw/` (JSON format, one per page)
- Cleaned text files in `data/cleaned/` (TXT format, one per page)
- Console logs showing progress
- Final metrics summary printed at the end

### Script 2: Query (`query.py`)

**Purpose:** Answer questions using the ingested data.

**Single question:**
```bash
python query.py --question "What is BizPay?"
```

**Batch questions from file:**
```bash
python query.py --questions test/questions.txt
```

**Concurrent batch processing:**
```bash
python query.py --questions test/questions.txt --concurrent
```

**Options:**
- `--question`: Single question to ask
- `--questions`: Path to file with questions (newline or JSON list)
- `--concurrent`: Process multiple questions concurrently (flag, default: false)

**Note:** All queries run concurrently without semaphore limits when using `--concurrent`

**What it does:**
1. Retrieves relevant chunks from vector database
2. Generates answer using Google Gemini
3. Formats answer with cited sources
4. Displays metrics (latency, tokens, cost)

## Complete Workflow: Ingestion + Webhook + Query Flow

### Step 1: Start Webhook Receiver (Terminal 1)

```bash
# Start webhook receiver to receive notifications
make start-webhook

# Or manually:
python webhook_receiver.py
```

**Output:**
```
INFO:     Started server process [XXXXX]
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

### Step 2: Start FastAPI Server (Terminal 2)

```bash
# Start FastAPI server
make start-api

# Or manually:
python fastapi_server.py
```

**Output:**
```
INFO:     Started server process [XXXXX]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Step 3: Ingest Data via API (Terminal 3)

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://www.transfi.com"],
    "callback_url": "http://localhost:8001/api/webhook"
  }'
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Ingestion started",
  "job_id": "uuid-here",
  "callback_url": "http://localhost:8001/api/webhook"
}
```

**Webhook notification** (received in Terminal 1):
```json
{
  "type": "ingestion",
  "status": "success",
  "job_id": "uuid-here",
  "urls": ["https://www.transfi.com"],
  "metrics": {
    "pages_scraped": 10,
    "total_chunks_created": 150,
    "total_tokens_processed": 50000,
    ...
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

### Step 4: Query via API (Terminal 3)

**Single query:**
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is BizPay?"
  }'
```

**Batch query with webhook:**
```bash
curl -X POST http://localhost:8000/api/query/batch \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      "What is BizPay?",
      "How does BizPay work?",
      "What are the key features of BizPay?"
    ],
    "callback_url": "http://localhost:8001/api/webhook"
  }'
```

**Webhook notification** (received in Terminal 1):
```
Question: What is BizPay?
Answer: BizPay is a unified, self-serve platform for global payments...
Sources:
  1.  - https://www.transfi.com/products/bizpay
     Snippet: "BizPay enables businesses to..."
...
```

### Alternative: CLI Workflow

```bash
# 1. Ingest data
python ingest.py --url https://www.transfi.com

# 2. Query single question
python query.py --question "What is BizPay?"

# 3. Query batch from file
python query.py --questions test/questions.txt

# 4. Query batch concurrently
python query.py --questions test/questions.txt --concurrent
```

## Sample Outputs

### Ingestion Output

```
INFO:core.ingestion_pipeline:Scraping started: url=https://www.transfi.com, page_types=['products', 'solutions'], max_depth=1
INFO:core.ingestion_pipeline:Scraping finished: pages=17, errors=0
INFO:core.ingestion_pipeline:Processing subpage: BizPay
INFO:core.ingestion_pipeline:Processing subpage: Checkout
...
INFO:core.ingestion_pipeline:Pipeline finished: pages=17, total_chunk_documents=360
INFO:core.ingestion_pipeline:Step scrape+process+embed: time=15.07s pages=17
INFO:core.ingestion_pipeline:Stored 360 chunk documents in vector DB
INFO:core.ingestion_pipeline:Step index: time=1.91s
INFO:core.ingestion_pipeline:Pipeline finished: total=17.34s pages=17 chunks=360 tokens=140846

=== Ingestion Metrics ===

Total Time: 17.34s
Pages Scraped: 17
Pages Failed: 0
Total Chunks Created: 360
Total Tokens Processed: 140,846
Embedding Generation Time: 15.07s
Indexing Time: 1.91s
Average Scraping Time per Page: 0.89s
Errors: None
```

### Single Query Output

```
Question: What is BizPay?

Answer: BizPay is a unified, self-serve platform for global payments and collections that helps businesses operating globally move money seamlessly in minutes across over 100 countries, ensuring global compliance and enterprise-grade security. It is a new platform for sending and receiving payments globally with low fees and 24/7 support.

Sources:
  1.  - https://www.transfi.com/products/bizpay
     Snippet: "bizpay bizpay offers instant onboarding, 3 - click transactions, low fees, and 24x7 support for businesses. transfi bizpay – send and receive money globally with ease transfi bi..."
  2.  - https://www.transfi.com/products/bizpay
     Snippet: "receive how it works 1 prefund wallet add funds to your wallet in preferred digital or fiat currency. 2 add contact details create an account and complete the quick verification..."
  3.  - https://www.transfi.com/products/bizpay
     Snippet: ", they allow you to start processing transactions instantly, eliminating lengthy setup and manual configuration. effortless user experience transfi ' s ai - powered single api s..."

Metrics:
  Total Latency: 3.42s
  Retrieval Time: 0.63s
  LLM Time: 2.77s
  Post-processing Time: 0.00s
  Documents Retrieved: 10
  Documents Used in Answer: 3
  Input Tokens: 2067
  Output Tokens: 64
  Estimated Cost: $0.0002
```

### Batch Query Output

```
Question: What is BizPay?

Answer: [Generated answer]

Sources:
  [Sources listed]

--------------------------------------------------------------------------------

Question: How does BizPay work?

Answer: [Generated answer]

Sources:
  [Sources listed]

--------------------------------------------------------------------------------

Metrics:
  Total Latency: 8.50s
  Retrieval Time: 1.25s
  LLM Time: 6.80s
  Post-processing Time: 0.45s
  Documents Retrieved: 10
  Documents Used in Answer: 6
  Input Tokens: 5234
  Output Tokens: 128
  Estimated Cost: $0.0005
```

### API Query Response

```json
{
  "question": "What is BizPay?",
  "answer": "BizPay is a unified, self-serve platform for global payments...",
  "citations": [
    {
      "url": "https://www.transfi.com/products/bizpay",
      "snippet": "BizPay enables businesses to..."
    }
  ],
  "metrics": {
    "total_latency_s": 3.42,
    "retrieval_time_s": 0.63,
    "llm_time_s": 2.77,
    "post_time_s": 0.0,
    "docs_retrieved": 10,
    "docs_used": 3,
    "input_tokens": 2067,
    "output_tokens": 64,
    "estimated_cost_usd": 0.0002
  }
}
```

### Webhook Payload (Ingestion)

```json
{
  "type": "ingestion",
  "status": "success",
  "job_id": "abc-123-def-456",
  "urls": ["https://www.transfi.com"],
  "metrics": {
    "total_time_seconds": 62.93,
    "pages_scraped": 10,
    "pages_failed": 0,
    "total_chunks_created": 150,
    "total_tokens_processed": 50000,
    "embedding_generation_time_seconds": 12.34,
    "indexing_time_seconds": 3.21,
    "average_scraping_time_per_page_seconds": 4.52
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

### Webhook Payload (Batch Query)

```json
{
  "type": "batch_query",
  "status": "success",
  "results": [
    {
      "question": "What is BizPay?",
      "answer": "...",
      "sources": [...],
      "metrics": {...}
    }
  ],
  "metrics": {
    "total_latency_s": 8.50,
    "retrieval_time_s": 1.25,
    "llm_time_s": 6.80,
    ...
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

## Configuration Options

### Ingestion Configuration

**Scraper settings** (in `core/scraper.py`):
- `max_concurrent`: Parameter kept for compatibility but not used (no semaphore)
- `delay`: Delay between requests in seconds (default: 0.1)
- `max_depth`: Maximum depth for depth-first scraping (default: 20, passed via CLI/API)
- Uses `aiohttp` connection pooling for concurrent requests

**Page types** (default in `core/ingestion_pipeline.py`):
- Default: `["products", "solutions"]`
- Can be configured in ingestion pipeline initialization

### Query Configuration

**Query Engine settings** (in `core/query_engine.py`):
- `TOP_K`: Number of chunks to retrieve (default: 10, class constant)
- `MODEL`: LLM model name (default: "gemini-2.5-flash")
- `SIMILARITY_THRESHOLD`: Not used (all retrieved documents passed to LLM)

**Concurrency**:
- All queries run concurrently without semaphore limits
- Uses `asyncio.gather()` for parallel execution

### API Configuration

**Server ports:**
- FastAPI server: Port 8000 (configurable in `fastapi_server.py`)
- Webhook receiver: Port 8001 (configurable in `webhook_receiver.py`)

**Webhook settings** (in `api/services.py`):
- `WEBHOOK_TIMEOUT`: 30 seconds
- `WEBHOOK_MAX_RETRIES`: 3 attempts
- `WEBHOOK_RETRY_DELAY`: 5 seconds base delay

### Embedding Configuration

**Model** (in `core/embeddings.py`):
- Default: `all-MiniLM-L6-v2`
- Chunk size: 400 tokens (with 80 token overlap)
- Location: `./models/all-MiniLM-L6-v2/` (auto-downloaded on first use)

## Makefile Commands

```bash
make help           # Show all available commands
make install        # Install dependencies from requirements.txt
make start-api      # Start FastAPI server on port 8000
make start-webhook  # Start webhook receiver on port 8001
make start-all      # Start both servers in background
make stop-all       # Stop all running servers
make clean          # Clean generated files (data/raw, data/cleaned)
make clean-all      # Clean all data including vector DB
```

## API Endpoints

### Root

```bash
GET http://localhost:8000/
```

Response:
```json
{"message": "RAG System is running"}
```

### Ingest Data

```bash
POST http://localhost:8000/api/ingest
Content-Type: application/json

{
  "urls": ["https://www.transfi.com"],
  "callback_url": "http://your-webhook-url/webhook"
}
```

### Single Query

```bash
POST http://localhost:8000/api/query
Content-Type: application/json

{
  "question": "What is BizPay?"
}
```

### Batch Query

```bash
POST http://localhost:8000/api/query/batch
Content-Type: application/json

{
  "questions": ["Question 1", "Question 2"],
  "callback_url": "http://your-webhook-url/webhook"  # optional
}
```

## Testing

### Test Questions File

Sample questions are provided in `test/questions.txt`:

```bash
# Run batch query with test file
python query.py --questions test/questions.txt

# Run with concurrent processing
python query.py --questions test/questions.txt --concurrent
```

## Data Storage

### Raw HTML Files

**Location:** `data/raw/`

**Format:** JSON files with structure:
```json
{
  "title": "BizPay",
  "main_url": "https://www.transfi.com/products/bizpay",
  "page_type": "products",
  "short_description": "...",
  "scraped_at": 1234567890.0,
  "html_contents": [
    {
      "url": "https://www.transfi.com/products/bizpay",
      "html": "<html>...</html>",
      "index": 0
    }
  ]
}
```

**Naming:** `{sanitized_title}.json` (HTML content stored within JSON)

### Cleaned Text Files

**Location:** `data/cleaned/`

**Format:** Plain text files (`.txt`)

**Naming:** `{sanitized_title}.txt`

### Vector Database

**Location:** `data/vector_db/`

**Database:** ChromaDB (SQLite-based)

**Collection:** `transfi_rag`

**Contents:** Document embeddings, metadata, chunks

## Architecture

### Layered Architecture

- **API Layer** (`fastapi_server.py`, `api/`): RESTful endpoints, request/response handling
- **Service Layer** (`api/services.py`): Business logic orchestration
- **Core Layer** (`core/`): Core functionality (scraping, processing, querying)

### Key Components

1. **AsyncWebScraper**: Depth-first web scraping with async HTTP requests
2. **TextProcessor**: HTML to text conversion and cleaning
3. **Embeddings**: Sentence-transformers for text embedding and chunking
4. **VectorDB**: ChromaDB singleton for vector storage (persistent)
5. **QueryEngine**: Singleton query engine with LLM integration
6. **LLMClient**: Google Gemini API client
7. **DataIngestionPipeline**: Orchestrates scraping, processing, embedding, and storage

### Singleton Pattern

- **VectorDB**: Single instance across the application
- **QueryEngine**: Module-level singleton for efficient model reuse

## Troubleshooting

### Common Issues

1. **Import errors:**
   - Ensure virtual environment is activated
   - Run `make install` to install dependencies

2. **Port already in use:**
   - Change port in `fastapi_server.py` or `webhook_receiver.py`
   - Use `make stop-all` to stop existing servers

3. **Vector DB errors:**
   - Delete `data/vector_db/` and re-run ingestion
   - Use `make clean-all` to reset everything

4. **Model download issues:**
   - Ensure internet connection for first-time model download
   - Model is cached in `models/` directory

## Requirements

See `requirements.txt` for complete dependencies.

**Key dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `chromadb` - Vector database (persistent)
- `sentence-transformers` - Embeddings (all-MiniLM-L6-v2)
- `google-generativeai` - Gemini API (gemini-2.5-flash)
- `aiohttp` - Async HTTP client
- `beautifulsoup4` - HTML parsing
- `click` - CLI framework
- `pydantic` - Data validation
- `trafilatura` - Text extraction from HTML
