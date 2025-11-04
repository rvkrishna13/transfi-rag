.PHONY: help install ingest query start-api start-webhook clean clean-all clean-cache clean-models clean-venv test package-src

# Default Python interpreter
PYTHON := python3

# Default values
API_PORT := 8000
WEBHOOK_PORT := 8001

help:  ## Show this help message
	@echo "Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

install:  ## Install dependencies from requirements.txt
	@echo "Installing dependencies..."
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Installation complete!"

start-api:  ## Start FastAPI server on port $(API_PORT)
	@echo "Starting FastAPI server on port $(API_PORT)..."
	$(PYTHON) fastapi_server.py

start-webhook:  ## Start webhook receiver on port $(WEBHOOK_PORT)
	@echo "Starting webhook receiver on port $(WEBHOOK_PORT)..."
	$(PYTHON) webhook_receiver.py

start-all:  ## Start both API and webhook receiver (in background)
	@echo "Starting FastAPI server and webhook receiver..."
	@$(MAKE) start-api & \
	$(MAKE) start-webhook & \
	echo "Both servers started. Use 'make stop-all' to stop them."

stop-all:  ## Stop all running servers
	@echo "Stopping all servers..."
	@pkill -f "fastapi_server.py" || true
	@pkill -f "webhook_receiver.py" || true
	@echo "Servers stopped."

clean:  ## Clean generated files (data/raw, data/cleaned) and caches
	@echo "Cleaning generated files..."
	@rm -rf data/raw data/cleaned
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .DS_Store
	@echo "Clean complete!"

clean-all:  ## Clean all data including vector DB and model cache
	@echo "Cleaning all data including vector DB..."
	@rm -rf data/
	@rm -rf models/all-MiniLM-L6-v2
	@echo "All data cleaned!"

clean-cache:  ## Clean Python caches (__pycache__, pytest cache)
	@echo "Cleaning Python caches..."
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .DS_Store
	@echo "Caches cleaned!"

clean-models:  ## Remove embedding model cache (will re-download on next run)
	@echo "Removing model cache..."
	@rm -rf models/all-MiniLM-L6-v2
	@echo "Model cache removed."

clean-venv:  ## Remove local virtualenv directory (transfi/) - IRREVERSIBLE
	@echo "Removing local virtualenv (transfi/)..."
	@rm -rf transfi/
	@echo "Virtualenv removed."

test:  ## Run tests (placeholder for future test suite)
	@echo "Running tests..."
	@echo "No tests configured yet."

lint:  ## Run linter (placeholder)
	@echo "Running linter..."
	@echo "No linter configured yet."

format:  ## Format code (placeholder)
	@echo "Formatting code..."
	@echo "No formatter configured yet."

package-src:  ## Create source-only zip (excludes data/, models/, venv, .git)
	@echo "Packaging source files into transfi-rag-src.zip..."
	@zip -r transfi-rag-src.zip api core *.py README.md requirements.txt Makefile tests questions.txt \
	  -x "data/**" "models/**" "transfi/**" \
	     ".git/**" "**/__pycache__/**" ".pytest_cache/**" ".DS_Store"
	@echo "Created transfi-rag-src.zip"

