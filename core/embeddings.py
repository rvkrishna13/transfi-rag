from typing import List, Dict
import asyncio
import logging
import os
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

# Suppress tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logger = logging.getLogger(__name__)

class Embeddings:
    def __init__(self, chunk_size: int = 400, overlap: int = 80, max_workers: int = 10):
        self.model_name = './models/all-MiniLM-L6-v2'
        self.model = SentenceTransformer(self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_workers = max_workers
        self.max_batch_size = 32

    def chunk_text(self, text: str) -> List[str]:
        tokens = self.tokenizer.tokenize(text)
        step = self.chunk_size - self.overlap if self.chunk_size > self.overlap else 1
        return [self.tokenizer.convert_tokens_to_string(tokens[i:i+self.chunk_size]) for i in range(0, len(tokens), step)]

    async def tokenize_documents(self, documents: List[str]) -> List[List[str]]:
        """
        Tokenize documents synchronously.
        Note: chunk_text is fast and doesn't need threading - transformers don't handle fork well.
        """
        results = []
        for document in documents:
            try:
                chunks = self.chunk_text(document)
                results.append(chunks)
            except Exception as e:
                logger.warning("Chunking error for document: %s", str(e))
                results.append([])
        return results

    async def encode_batch(self, chunked_document: List[str]) -> List[List[float]]:
        """
        Encode batch of chunks synchronously.
        Note: model.encode runs synchronously - transformers don't handle fork/thread well.
        """
        all_embeddings = []
        
        batches = [chunked_document[i:i+self.max_batch_size] for i in range(0, len(chunked_document), self.max_batch_size)]
        
        for batch in batches:
            try:
                emb = self.model.encode(batch, normalize_embeddings=True)
                if hasattr(emb, 'tolist'):
                    emb_list = emb.tolist()
                elif isinstance(emb, list):
                    emb_list = emb
                else:
                    emb_list = list(emb)
                if emb_list and isinstance(emb_list[0], list):
                    all_embeddings.extend(emb_list)
                else:
                    all_embeddings.append(emb_list)
            except Exception as e:
                logger.warning("Encoding error: %s", str(e))
        
        return all_embeddings

    async def create_embeddings_with_text(self, documents: List[str]) -> List[Dict[str, List]]:
        """
        For each input document, return both the chunked texts and their embeddings.
        Output shape per document: { 'chunks': List[str], 'embeddings': List[List[float]] }
        """
        chunked_documents = await self.tokenize_documents(documents)
        results: List[Dict[str, List]] = []
        for chunk_texts in chunked_documents:
            vectors = await self.encode_batch(chunk_texts)
            results.append({
                'chunks': chunk_texts,
                'embeddings': vectors,
            })
        return results
    
    def get_text_embeddings(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True)