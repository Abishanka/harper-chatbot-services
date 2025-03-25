from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
import openai
import numpy as np
from supabase import create_client, Client
import os

from app.utils.config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY
from app.utils.text_processing import create_embedding

router = APIRouter()

# Create OpenAI client
openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

class ChatRequest(BaseModel):
    query: str
    workspace_id: str
    user_id: Optional[str] = None
    max_context_chunks: Optional[int] = 10

class MediaContext(BaseModel):
    media_id: str
    media_name: str
    chunk_id: str
    chunk_text: str
    similarity: float

class ChatResponse(BaseModel):
    answer: str
    context_sources: List[MediaContext]

# Function to match documents using cosine distance
async def match_documents(query_embedding, match_threshold=0.35, match_count=20):
    result = supabase.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "match_threshold": match_threshold,
        "match_count": match_count
    }).execute()

    print(f"Match documents result: {result}")
    
    # # Check if the result has an error
    # if result.status_code != 200:
    #     raise HTTPException(status_code=result.status_code, detail=f"Database error: {result.data}")

    return result.data

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    RAG-powered chat endpoint.
    1. Vectorizes user query
    2. Retrieves top 25 similar embeddings from the database
    3. Filters to embeddings in the user's workspace
    4. Uses top chunks as context for LLM generation
    5. Returns answer and source information
    """
    try:
        # Extract user_id from auth if not provided
        user_id = request.user_id
        if not user_id:
            auth_header = req.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                # TODO: Extract user ID from token in a real implementation.
                raise HTTPException(status_code=401, detail="User ID extraction not implemented")
            else:
                raise HTTPException(status_code=401, detail="Authentication required")

        # 1. Create embedding for the query (do not modify this utility call)
        query_embedding = await create_embedding(request.query, openai_client)
        
        # 2. Fetch top similar vector embeddings using the new match_documents function
        vector_search_result = await match_documents(query_embedding)

        print(f"Vector search result: {vector_search_result}")

        # Check if the vector search result is empty
        if not vector_search_result:
            completion = await openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": request.query}
                ]
            )
            return ChatResponse(
                answer=completion.choices[0].message.content,
                context_sources=[]
            )
                
        # 3. Get all media IDs in the user's workspace.
        workspace_media_result = supabase.from_("media_workspace_mapping").select("media_id").eq("workspace_id", request.workspace_id).execute()
        
        workspace_media_ids = [item['media_id'] for item in workspace_media_result.data] if workspace_media_result.data else []

        print(f"Workspace media IDs: {workspace_media_ids}")

        # If no media IDs found in the workspace, run the query through the LLM
        if not workspace_media_ids:
            completion = await openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": request.query}
                ]
            )
            return ChatResponse(
                answer=completion.choices[0].message.content,
                context_sources=[]
            )
        
        # Filter vector search results to only include media in the workspace
        filtered_results = [
            result for result in vector_search_result 
            if result['media_id'] in workspace_media_ids
        ]
        filtered_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # 4. Use the top chunks as context for LLM
        max_chunks = min(10, len(filtered_results))  # Limit to a maximum of 10 chunks
        top_chunks = filtered_results[:max_chunks]

        print(f"Top chunks: {top_chunks}")
        
        # Build context from top chunks; adjust media name extraction since it is nested in 'media'
        context = ""
        context_sources = []
        for chunk in top_chunks:
            media_name = chunk.get('media', {}).get('name', 'Unknown')
            context += f"\n\nContext from {media_name}:\n{chunk['chunk_text']}\n"
            context_sources.append(MediaContext(
                media_id=chunk['media_id'],
                media_name=media_name,
                chunk_id=chunk['id'],
                chunk_text=chunk['chunk_text'],
                similarity=chunk['similarity']
            ))
        
        print(f"Context sources: {context_sources}")

        # 5. Generate answer from LLM using the provided context
        system_prompt = """You are a helpful assistant that answers questions based on the provided context.
        If the context doesn't contain relevant information to answer the question, state that you don't have enough information.
        Cite the source of your information when possible. Try to use as much information as possible to answer the question. You can use knowledge 
        outside of the context if needed. The context is a collection of documents that are related to the question.
        """
        
        user_prompt = f"Context information:\n{context}\n\nQuestion: {request.query}\n\nPlease provide a helpful response based on the context."
        
        completion = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # 6. Return the answer and source information
        return ChatResponse(
            answer=completion.choices[0].message.content,
            context_sources=context_sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
