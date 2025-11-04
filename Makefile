.PHONY: help install ingest query start-api start-webhook clean test

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

clean:  ## Clean generated files (data/raw, data/cleaned, but keep data/vector_db)
	@echo "Cleaning generated files..."
	@rm -rf data/raw data/cleaned
	@echo "Clean complete!"

clean-all:  ## Clean all data including vector DB
	@echo "Cleaning all data including vector DB..."
	@rm -rf data/
	@echo "All data cleaned!"

test:  ## Run tests (placeholder for future test suite)
	@echo "Running tests..."
	@echo "No tests configured yet."

lint:  ## Run linter (placeholder)
	@echo "Running linter..."
	@echo "No linter configured yet."

format:  ## Format code (placeholder)
	@echo "Formatting code..."
	@echo "No formatter configured yet."

