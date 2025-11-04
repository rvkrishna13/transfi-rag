#!/usr/bin/env python3
"""
CLI script for data ingestion.
"""
import os
# Suppress tokenizers parallelism warning - must be set before any imports
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import asyncio
import logging
import warnings

import click

from core.ingestion_pipeline import DataIngestionPipeline
from core.utils import format_ingestion_metrics

# Suppress warnings globally in terminal output
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*importlib.metadata.*")
warnings.filterwarnings("ignore", message=".*packages_distributions.*")

# Concise base logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option('--url', required=True, help='Website URL to ingest data from')
def main(url: str):
    """
    Scrape website, process content, create embeddings, and store in vector database.
    
    Example:
        python ingest.py --url https://example.com
    """
    
    async def run():
        pipeline = DataIngestionPipeline()
        
        page_types_list = ["products", "solutions"]
        
        result = await pipeline.run(url=url, page_types=page_types_list)
        
        metrics = result.get("metrics", {})
        print("\n" + format_ingestion_metrics(metrics) + "\n")
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
