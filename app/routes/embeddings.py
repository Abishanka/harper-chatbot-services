from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import openai
from typing import List, Optional
import numpy as np
import json

from app.utils.config import OPENAI_API_KEY
from app.utils.text_processing import create_embedding

router = APIRouter()

# Create OpenAI client
openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


class SearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 5
    similarity_threshold: Optional[float] = 0.35


class SearchResult(BaseModel):
    chunk_id: str
    chunk_text: str
    similarity: float
    media_id: str
    page_number: Optional[int]


@router.post("/search", response_model=List[SearchResult])
async def search_embeddings(query: SearchQuery):
    """
    Search for similar text chunks using embeddings
    """
    try:
        # Create embedding for the search query
        query_embedding = await create_embedding(query.query, openai_client)
        
        # Convert query embedding to numpy array for similarity calculation
        query_embedding_array = np.array(query_embedding)
        
        # Get all chunks with their embeddings
        # Note: In a production environment, you'd want to implement this using
        # a vector similarity search database like pgvector
        from app.utils.config import supabase
        chunks_result = supabase.table('chunks').select('*').execute()
        
        if not chunks_result.data:
            return []
        
        # Calculate similarities and sort results
        results = []
        for chunk in chunks_result.data:
            # Parse stored embedding back to list
            chunk_embedding = json.loads(chunk['embedding'])
            chunk_embedding_array = np.array(chunk_embedding)
            
            # Calculate cosine similarity
            similarity = np.dot(query_embedding_array, chunk_embedding_array) / (
                np.linalg.norm(query_embedding_array) * np.linalg.norm(chunk_embedding_array)
            )
            
            if similarity >= query.similarity_threshold:
                results.append(SearchResult(
                    chunk_id=chunk['id'],
                    chunk_text=chunk['chunk_text'],
                    similarity=float(similarity),
                    media_id=chunk['media_id'],
                    page_number=chunk.get('page_number')
                ))
        
        # Sort by similarity (highest first) and limit results
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:query.limit]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-embed")
async def batch_embed_text(texts: List[str]):
    """
    Create embeddings for multiple texts in one batch
    """
    try:
        embeddings = []
        for text in texts:
            embedding = await create_embedding(text, openai_client)
            embeddings.append(embedding)
            
        return {"success": True, "embeddings": embeddings}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 