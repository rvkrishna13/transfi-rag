from typing import List
from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    title: str
    url: str
    tags: List[str] = []
    short_description: str
    long_description: str


class Document(BaseModel):
    id: str
    text: str
    embeddings: List[List[float]]
    chunks: List[str]
    metadata: DocumentMetadata


