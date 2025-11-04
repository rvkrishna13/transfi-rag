from typing import List, Optional
import threading
import chromadb
from chromadb.config import Settings

from core.document import Document


class VectorDB:
    """Singleton vector database using ChromaDB."""
    
    _instance = None
    _lock = threading.Lock()
    _write_lock = threading.Lock()
    
    def __new__(
        cls,
        collection_name: str = "transfi_rag",
        persist_directory: str = "./data/vector_db"
    ):
        """Singleton pattern - returns the same instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(VectorDB, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        collection_name: str = "transfi_rag",
        persist_directory: str = "./data/vector_db"
    ):
        """Initialize ChromaDB client and collection (only once)."""
        if self._initialized:
            return
            
        with VectorDB._lock:
            if self._initialized:
                return
                
            self.collection_name = collection_name
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
            
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._initialized = True
    
    async def add_data(self, documents: List[Document]) -> None:
        """
        Add documents with multiple chunks to the database.
        
        Expects:
            - doc.text: List[str] (list of chunk texts)
            - doc.embeddings: List[List[float]] (list of embeddings, one per chunk)
        
        Stores each chunk as separate entry with metadata tracking parent document.
        """

        if not documents:
            return
        
        all_ids = []
        all_embeddings = []
        all_texts = []
        all_metadatas = []
        
        for doc in documents:
            texts = doc.chunks if getattr(doc, 'chunks', None) else (doc.text if isinstance(doc.text, list) else [doc.text])
            embeddings = doc.embeddings if isinstance(doc.embeddings[0], list) else [doc.embeddings]

            pair_count = min(len(texts), len(embeddings))
            
            for chunk_idx, (chunk_text, chunk_embedding) in enumerate(zip(texts[:pair_count], embeddings[:pair_count])):
                chunk_id = f"{doc.id}_chunk_{chunk_idx}"
                
                chunk_metadata = doc.metadata.model_dump()
                chunk_metadata.update({
                    'parent_doc_id': doc.id,
                    'chunk_index': chunk_idx,
                    'total_chunks': len(texts)
                })

                for k, v in list(chunk_metadata.items()):
                    if isinstance(v, list):
                        try:
                            chunk_metadata[k] = ", ".join(map(str, v))
                        except Exception:
                            chunk_metadata[k] = str(v)
                    elif not isinstance(v, (str, int, float, bool)) and v is not None:
                        chunk_metadata[k] = str(v)
                
                all_ids.append(chunk_id)
                all_embeddings.append(chunk_embedding)
                all_texts.append(chunk_text)
                all_metadatas.append(chunk_metadata)
        
        self.collection.add(
            ids=all_ids,
            embeddings=all_embeddings,
            documents=all_texts,
            metadatas=all_metadatas
        )
    
    def query_by_embeddings(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> dict:
        """
        Query using embeddings.
        
        Returns: {
            'ids': [['doc_001', 'doc_002']],
            'documents': [['text1', 'text2']],
            'metadatas': [[{...}, {...}]],
            'distances': [[0.1, 0.2]]
        }
        """
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where
        )
    
    async def drop_collection(self) -> None:
        """Remove all rows from the collection without deleting it."""
        try:
            # Delete all records by empty filter
            self.collection.delete(where={})
        except Exception:
            # Fallback: fetch ids in batches and delete
            try:
                offset = 0
                batch = 1000
                while True:
                    got = self.collection.get(include=["ids"], limit=batch, offset=offset)
                    ids = got.get("ids") or []
                    if not ids:
                        break
                    self.collection.delete(ids=ids)
                    offset += len(ids)
            except Exception:
                # If clearing fails, recreate collection as last resort
                self.client.delete_collection(name=self.collection_name)
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
    
    async def ingest_data(self, documents: List[Document]) -> None:
        """Ingest data into the vector database."""
        async with self.write_lock:
            await self.drop_collection()
            await self.add_data(documents)