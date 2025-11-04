"""
Core ingestion pipeline logic.
Handles the complete pipeline: scrape -> process -> embed -> store.
"""
import asyncio
import logging
import time
import re
import json
from pathlib import Path
from typing import List
from dataclasses import asdict

from core.embeddings import get_embeddings
from core.text_processor import TextProcessor
from core.document import Document, DocumentMetadata
from core.vector_db import VectorDB
from core.scraper import AsyncWebScraper
import time

logger = logging.getLogger(__name__)


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize a string to be used as a filename."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    sanitized = sanitized.replace(' ', '_')
    sanitized = re.sub(r'_+', '_', sanitized)
    sanitized = sanitized.strip('._')
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    if not sanitized:
        sanitized = "page"
    return sanitized


def save_raw_html(pages: List[dict], base_dir: str = "data/raw") -> None:
    """
    Save raw HTML content to a single structured file per page.
    Each file contains JSON with metadata and HTML contents mapped to their source URLs.
    """
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    
    for page in pages:
        title = page.get("title", "unknown")
        filename = sanitize_filename(title)
        raw_contents = page.get("long_description_raw", [])
        urls = page.get("long_description_source_urls", [])
        
        page_data = {
            "title": title,
            "main_url": page.get("url", ""),
            "page_type": page.get("page_type", ""),
            "short_description": page.get("short_description", ""),
            "scraped_at": page.get("scraped_at", 0),
            "html_contents": [
                {
                    "url": url,
                    "html": html_content,
                    "index": idx
                }
                for idx, (html_content, url) in enumerate(zip(raw_contents, urls))
            ]
        }
        
        json_filepath = Path(base_dir) / f"{filename}.json"
        try:
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)
            logger.debug("Saved raw HTML (JSON): %s", json_filepath)
        except Exception as e:
            logger.warning("Failed to save raw HTML for %s: %s", title, str(e))


def save_cleaned_text(pages: List[dict], processed_bodies: List[str], base_dir: str = "data/cleaned") -> None:
    """Save cleaned text content to files using subpage names as filenames."""
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    
    for page, cleaned_text in zip(pages, processed_bodies):
        title = page.get("title", "unknown")
        filename = sanitize_filename(title)
        filepath = Path(base_dir) / f"{filename}.txt"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
            logger.debug("Saved cleaned text: %s", filepath)
        except Exception as e:
            logger.warning("Failed to save cleaned text for %s: %s", title, str(e))


class DataIngestionPipeline:
    """Handles the complete pipeline: scrape -> process -> embed -> store."""
    
    def __init__(self, clear_collection: bool = True, max_depth: int = 3):
        self.text_processor = TextProcessor()
        self.embeddings = get_embeddings()
        self.vector_db = VectorDB()
        self.max_depth = max_depth
    
    async def scrape_pages(
        self, 
        url: str, 
        page_types: List[str] = None
    ) -> tuple[List[dict], dict, List[Document]]:
        """
        Scrape pages, process them through pipeline, and return data + stats + documents.
        
        Returns:
            tuple: (pages_dict, stats, all_documents)
                - pages_dict: List of page dictionaries
                - stats: Scraping statistics
                - all_documents: List of all Document objects created (one per chunk)
        """
        async with AsyncWebScraper(max_depth=self.max_depth) as scraper:
            logger.info("Scraping started: url=%s, page_types=%s, max_depth=%s", url, page_types, self.max_depth)
            pages = await scraper.discover_and_scrape_pages(
                url,
                page_types=page_types or ["products", "solutions"]
            )
            stats = scraper.get_stats()
        
        logger.info("Scraping finished: pages=%d, errors=%d", len(pages), len(stats.get('errors', [])))
        
        pages_dict = []
        for p in pages:
            if isinstance(p, dict):
                pages_dict.append(p)
            else:
                pages_dict.append(p.__dict__ if hasattr(p, '__dict__') else asdict(p))
        
        all_documents = []
        tasks = [self.process_subpage(page_dict) for page_dict in pages_dict]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for page_dict, result in zip(pages_dict, results):
            if isinstance(result, list):
                all_documents.extend(result)
            elif isinstance(result, Exception):
                logger.error("Error processing page %s: %s", page_dict.get('title', 'unknown'), str(result))
        
        logger.info("Pipeline finished: pages=%d, total_chunk_documents=%d", len(pages_dict), len(all_documents))
        
        return pages_dict, stats, all_documents

    async def process_subpage(self, sub_page: dict) -> List[Document]:
        """
        Process a single subpage: fetch HTML, clean HTML, generate embeddings, and create documents.
        Note: Documents are NOT stored here - they will be stored in batch after all pages are processed.
        
        Args:
            sub_page: Dictionary with keys: title, url, short_description, page_type
        
        Returns:
            List[Document]: List of documents (one per chunk) that were created (not yet stored)
        """
        logger.info("Processing subpage: %s", sub_page.get("title", "unknown"))
        
        url = sub_page.get("url", "")
        if not url:
            logger.warning("No URL found for subpage: %s", sub_page.get("title", "unknown"))
            return []
        
        async with AsyncWebScraper(max_depth=1) as scraper:
            raw_contents, raw_content_urls = await scraper.dfs_scrape_related_pages(url, sub_page.get("page_type", ""))
        
        sub_page["long_description_raw"] = raw_contents
        sub_page["long_description_source_urls"] = raw_content_urls
        sub_page["scraped_at"] = time.time()
        
        processed = self.text_processor.process_in_batches([raw_contents])
        processed_body = '\n'.join(processed[0]) if processed else ""
        
        combined_content = '\n\n'.join(filter(None, [
            sub_page.get("title", ""),
            sub_page.get("short_description", ""),
            processed_body
        ]))
        
        save_raw_html([sub_page], "data/raw")
        save_cleaned_text([sub_page], [processed_body], "data/cleaned")
        
        embedding_result = await self.embeddings.create_embeddings_with_text([combined_content])
        embedding_data = embedding_result[0]
        embeddings = embedding_data['embeddings']
        chunked_texts = embedding_data['chunks']
        
        embedding_as_lists = [vec.tolist() if hasattr(vec, "tolist") else list(vec) for vec in embeddings]
        
        title = sub_page.get('title', 'unknown')
        sanitized_title = sanitize_filename(title)[:30]
        page_type = sub_page.get('page_type', 'page')
        base_doc_id = f"{page_type}_{sanitized_title}"
        
        base_metadata = DocumentMetadata(
            title=sub_page.get("title", ""),
            url=sub_page.get("url", ""),
            tags=[sub_page.get("page_type", "")] if sub_page.get("page_type") else [],
            short_description=sub_page.get("short_description", ""),
            long_description=processed_body,
        )
        
        documents = []
        for chunk_idx, (chunk_text, chunk_embedding) in enumerate(zip(chunked_texts, embedding_as_lists)):
            chunk_doc_id = f"{base_doc_id}_chunk_{chunk_idx}"
            
            document = Document(
                id=chunk_doc_id,
                text=chunk_text,
                metadata=base_metadata,
                embeddings=[chunk_embedding],
                chunks=[chunk_text]
            )
            documents.append(document)
        
        return documents
        

    async def run(
        self, 
        url: str,
        page_types: List[str] = None
    ) -> dict:
        """
        Run the complete pipeline and return metrics.
        Now uses the new pipeline() function which processes, embeds, and stores each page.
        """
        start_time = time.time()
        pipeline_errors = []

        scrape_start = time.time()
        try:
            pages, stats, all_documents = await self.scrape_pages(url, page_types)
        except Exception as e:
            pipeline_errors.append({
                'type': 'scrape_pipeline_error',
                'message': str(e)
            })
            raise
        scrape_time = time.time() - scrape_start
        logger.info("Step scrape+process+embed: time=%.2fs pages=%d", scrape_time, len(pages))

        index_start = time.time()
        try:
            if all_documents:
                await self.vector_db.add_documents(all_documents)
                logger.info("Stored %d chunk documents in vector DB", len(all_documents))
        except Exception as e:
            pipeline_errors.append({
                'type': 'vector_db_error',
                'message': str(e)
            })
            logger.error("Failed to store documents in vector DB: %s", str(e))
        index_time = time.time() - index_start
        logger.info("Step index: time=%.2fs", index_time)

        total_chunks = len(all_documents)
        tokenizer = self.embeddings.tokenizer
        total_tokens = 0
        for doc in all_documents:
            chunks = getattr(doc, 'chunks', None)
            if isinstance(chunks, list) and chunks:
                total_tokens += sum(len(tokenizer.tokenize(c)) for c in chunks)
            else:
                total_tokens += len(tokenizer.tokenize(doc.text))

        total_time = time.time() - start_time

        pages_scraped = len(pages)
        pages_scraped_success = stats.get('pages_scraped_success', pages_scraped)
        pages_failed = max(0, stats.get('total_subpages', pages_scraped) - pages_scraped_success)
        avg_scrape_time_per_page = (scrape_time / pages_scraped) if pages_scraped else 0.0

        result = {
            "metrics": {
                "total_time_seconds": round(total_time, 2),
                "pages_scraped": pages_scraped,
                "pages_failed": pages_failed,
                "total_chunks_created": total_chunks,
                "total_tokens_processed": total_tokens,
                "embedding_generation_time_seconds": round(scrape_time, 2),
                "indexing_time_seconds": round(index_time, 2),
                "average_scraping_time_per_page_seconds": round(avg_scrape_time_per_page, 2),
                "errors": (stats.get('errors', []) + pipeline_errors),
            },
        }
        logger.info(
            "Pipeline finished: total=%.2fs pages=%d chunks=%d tokens=%d",
            total_time, pages_scraped, total_chunks, total_tokens,
        )
        return result

