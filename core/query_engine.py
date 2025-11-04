"""
Core query engine logic for RAG system.
"""
import time
import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel

from core.embeddings import get_embeddings
from core.vector_db import VectorDB
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class QueryMetrics(BaseModel):
    """Metrics for a query operation."""
    total_latency_s: float
    retrieval_time_s: float
    llm_time_s: float
    post_time_s: float
    docs_retrieved: int
    docs_used: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class QueryEngine:
    """Query engine for RAG system."""
    
    TOP_K = 10  # Increased to retrieve more documents for better coverage
    MODEL = "gemini-2.5-flash"
    SIMILARITY_THRESHOLD = 0.7  # Cosine similarity threshold (lower distance = higher similarity)
    
    def __init__(self):
        """Initialize query engine with singleton instances."""
        self.embeddings = get_embeddings()
        self.vectordb = VectorDB()
        self.llm = LLMClient(model=self.MODEL)
        logger.info("QueryEngine initialized - model loaded into memory")
    
    def create_rag_prompt(self, question: str, context_blocks: List[Tuple[str, Dict[str, Any]]]) -> str:
        """Create RAG prompt from question and context blocks."""
        context_strs = []
        for idx, (text, meta) in enumerate(context_blocks, start=1):
            url = meta.get("url", "")
            title = meta.get("title", "")
            context_strs.append(f"[Source {idx}] {title} - {url}\n{text}")
        context_blob = "\n\n".join(context_strs)
        return (
            "You are a knowledgeable assistant. Answer the user's question based on the provided sources. "
            "Use the information from the sources to construct a helpful and informative answer.\n\n"
            "Instructions:\n"
            "- Synthesize information from the sources to answer the question thoroughly\n"
            "- If sources contain partial information, provide what's available and explain the topic based on that context\n"
            "- Do not include citation markers like [1] or [Source 1] in your answer\n"
            "- Write in a clear, natural, and confident tone\n"
            "- Focus on being helpful and informative\n\n"
            f"Sources:\n{context_blob}\n\n"
            f"Question: {question}\n\n"
        )

    async def retrieve_documents(self, query: str) -> Dict[str, Any]:
        """Retrieve relevant documents from vector database."""
        start = time.time()
        logger.info("Retrieval started (top_k=%d) for query: %s", self.TOP_K, query[:100])
        vector = self.embeddings.get_text_embeddings(query)
        try:
            vector = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        except Exception:
            pass
        results = self.vectordb.query_by_embeddings([vector], n_results=self.TOP_K)
        retrieval_latency = time.time() - start

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        logger.info(
            "Retrieval finished in %.3fs: retrieved %d documents (distances: %s)",
            retrieval_latency,
            len(docs),
            [round(d, 3) for d in distances[:5]] if distances else "N/A"
        )

        return {
            "latency": retrieval_latency,
            "documents": docs,
            "metadatas": metas,
            "distances": distances,
        }

    def create_citations(self, docs: List[str], metas: List[Dict[str, Any]], max_citations: int = 3) -> List[Dict[str, Any]]:
        """Create citation objects from documents and metadata."""
        citations: List[Dict[str, Any]] = []
        for text, meta in list(zip(docs, metas))[:max_citations]:
            snippet = text.strip()
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            citations.append({
                "url": meta.get("url", ""),
                "title": meta.get("title", meta.get("short_description", "Source")),
                "snippet": snippet,
            })
        return citations

    async def answer_question(self, question: str) -> Dict[str, Any]:
        """Answer a single question using RAG."""
        t0 = time.time()

        retrieval = await self.retrieve_documents(question)
        docs = retrieval["documents"]
        metas = retrieval["metadatas"]
        distances = retrieval.get("distances", [])
        retrieval_time = retrieval["latency"]

        # If no documents retrieved, it means the vector DB is empty
        if not docs:
            logger.warning("No documents retrieved - vector database may be empty for question: %s", question)
            return {
                "question": question,
                "answer": "I don't know. No information is available in the knowledge base. Please ensure data has been ingested.",
                "citations": [],
                "metrics": QueryMetrics(
                    total_latency_s=round(time.time() - t0, 2),
                    retrieval_time_s=round(retrieval_time, 2),
                    llm_time_s=0.0,
                    post_time_s=0.0,
                    docs_retrieved=0,
                    docs_used=0,
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=0.0,
                ),
            }
        
        # Use all retrieved documents - let LLM decide relevance
        # Similarity threshold filtering removed to ensure we always pass documents to LLM
        # The LLM is better at determining if documents contain the answer
        filtered_docs = docs
        filtered_metas = metas
        
        logger.info(
            "Using %d documents for LLM (distances: %s)",
            len(filtered_docs),
            [round(d, 3) for d in distances[:5]] if distances else "N/A"
        )

        context_blocks: List[Tuple[str, Dict[str, Any]]] = list(zip(filtered_docs, filtered_metas))
        prompt = self.create_rag_prompt(question, context_blocks)

        llm_start = time.time()
        content, input_tokens, output_tokens = await self.llm.generate(
            system_prompt="You provide concise, accurate answers with citations.",
            user_prompt=prompt,
        )
        llm_time = time.time() - llm_start
        logger.info("LLM generation time: %.3fs", llm_time)

        post_start = time.time()
        citations = self.create_citations(filtered_docs, filtered_metas)
        post_time = time.time() - post_start

        total_time = time.time() - t0
        metrics = QueryMetrics(
            total_latency_s=round(total_time, 2),
            retrieval_time_s=round(retrieval_time, 2),
            llm_time_s=round(llm_time, 2),
            post_time_s=round(post_time, 2),
            docs_retrieved=len(docs),
            docs_used=len(citations),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=self.llm.estimate_cost(input_tokens, output_tokens),
        )

        return {
            "question": question,
            "answer": content,
            "citations": citations,
            "metrics": metrics,
        }

    async def run_queries(
        self,
        questions: List[str],
        concurrent: bool = False,
    ) -> List[Dict[str, Any]]:
        """Run multiple queries, optionally concurrently."""
        questions = [q.strip() for q in questions if q and q.strip()]
        if concurrent:
            # Run all queries concurrently
            tasks = [self.answer_question(q) for q in questions]
            return await asyncio.gather(*tasks)
        else:
            # Run queries sequentially (one after another)
            results = []
            for q in questions:
                result = await self.answer_question(q)
                results.append(result)
            return results


_engine_instance = QueryEngine()

__all__ = ['QueryMetrics', 'QueryEngine', 'get_query_engine']


def get_query_engine() -> QueryEngine:
    """Get the singleton QueryEngine instance (module-level)."""
    return _engine_instance
