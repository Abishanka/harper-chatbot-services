from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from pydantic import BaseModel
import os
import openai
from supabase import create_client, Client
import tempfile
from typing import List, Optional, Dict, Any
import uuid
import json

from app.utils.config import OPENAI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, STORAGE_BUCKET
from app.utils.text_processing import split_into_chunks, process_document_with_docling, create_embedding

router = APIRouter()

# Create OpenAI client
openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


class ChunkMetadata(BaseModel):
    headings: List[str] = []
    page_number: Optional[int] = None
    content_type: Optional[str] = None


class ChunkData(BaseModel):
    text: str
    metadata: ChunkMetadata


class TableData(BaseModel):
    id: str
    content: str
    html: Optional[str] = None


class FigureData(BaseModel):
    id: str
    caption: Optional[str] = None
    content: Optional[str] = None


class DocumentStructure(BaseModel):
    headings: List[str] = []
    sections: List[Dict[str, Any]] = []


class ProcessedDocument(BaseModel):
    text: str
    metadata: Dict[str, Any] = {}
    tables: List[TableData] = []
    figures: List[FigureData] = []
    structure: DocumentStructure


class ProcessChunkRequest(BaseModel):
    fileName: str


class ChunkResult(BaseModel):
    chunkId: str
    pageNumber: Optional[int] = None
    metadata: ChunkMetadata


class ProcessChunkResponse(BaseModel):
    success: bool
    chunks: int
    results: List[ChunkResult]
    tables: List[TableData]
    figures: List[FigureData]
    structure: DocumentStructure
    note: str


# Background task function to process chunks
async def background_process_chunks(file_name: str):
    process_chunk_request = ProcessChunkRequest(fileName=file_name)
    await process_chunks(process_chunk_request)

@router.post("/upload-file")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), owner_id: str = Form(...), workspace_id: str = Form(...)):
    """
    Upload a file to Supabase storage and create a media record
    """
    try:
        # Ensure the user is authenticated
        if not owner_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Generate a unique filename
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # Read file content
        content = await file.read()
        
        # Upload to Supabase storage
        storage_path = f"uploads/{unique_filename}"
        upload_result = supabase.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            content
        )
        
        # Create media record
        media_data = {
            'name': unique_filename,
            'original_name': file.filename,  # Ensure this column exists in the database
            'media_type': 'file',
            'owner_id': owner_id,
            'storage_path': storage_path
        }
        
        media_result = supabase.table('media').insert(media_data).execute()
        
        if not media_result.data:
            raise HTTPException(status_code=500, detail="Failed to create media record")
        
        # Insert into media_workspace_mapping
        media_id = media_result.data[0]['id']
        mapping_data = {
            'media_id': media_id,
            'workspace_id': workspace_id
        }

        mapping_result = supabase.table('media_workspace_mapping').insert(mapping_data).execute()
        
        if not mapping_result.data:
            raise HTTPException(status_code=500, detail="Failed to create media workspace mapping record")
        
        # Trigger background processing of chunks
        background_tasks.add_task(background_process_chunks, storage_path)

        return {
            "success": True,
            "fileName": storage_path,
            "mediaId": media_id
        }
        
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-chunks", response_model=ProcessChunkResponse)
async def process_chunks(request: ProcessChunkRequest):
    """
    Process a document by splitting it into chunks and creating embeddings
    """
    try:
        # Validate input
        if not request.fileName:
            raise HTTPException(status_code=400, detail="File name is required")
        
        # Get file data from storage
        try:
            file_result = supabase.storage.from_(STORAGE_BUCKET).download(request.fileName)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Failed to download file: {str(e)}")
        
        if not file_result:
            raise HTTPException(status_code=404, detail="File not found in storage")
        
        # Get media info from database based on filename
        file_name_only = os.path.basename(request.fileName)
        media_result = supabase.table('media').select('id, media_type, owner_id').eq('name', file_name_only).execute()
        
        if not media_result.data or len(media_result.data) == 0:
            raise HTTPException(status_code=404, detail="Media record not found")
        
        media_data = media_result.data[0]
        media_id = media_data['id']
        media_type = media_data['media_type']
        file_ext = os.path.splitext(request.fileName)[1].lower()[1:]

        print(f"Processing file: {request.fileName}")
        
        # Save file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_result)
        
        try:
            # Process document using Docling
            doc_result = await process_document_with_docling(temp_file_path, file_ext)
            
            if "error" in doc_result:
                raise HTTPException(status_code=500, detail=doc_result["error"])
            
            # Split text into chunks
            chunks = split_into_chunks(doc_result["text"])
            
            # Create embeddings and store in database
            results = []
            
            for chunk in chunks:
                # Create embedding
                embedding = await create_embedding(chunk["text"], openai_client)

                # Store chunk and embedding in database without metadata
                chunk_data = {
                    'chunk_text': chunk["text"],
                    'media_id': media_id,
                    'page_number': None,  # Set to None if not used
                    'embedding': json.dumps(embedding)
                    # Removed 'metadata' field
                }
                
                chunk_result = supabase.table('chunks').insert(chunk_data).execute()
                
                if not chunk_result.data or len(chunk_result.data) == 0:
                    raise HTTPException(status_code=500, detail="Failed to store chunk")
                
                chunk_id = chunk_result.data[0]['id']
                results.append(ChunkResult(
                    chunkId=chunk_id,
                    pageNumber=None,  # Set to None if not used
                    metadata=ChunkMetadata()  # Empty metadata
                ))
            
            return ProcessChunkResponse(
                success=True,
                chunks=len(results),
                results=results,
                tables=[TableData(**table) for table in doc_result["tables"]],
                figures=[FigureData(**figure) for figure in doc_result["figures"]],
                structure=DocumentStructure(**doc_result["structure"]),
                note="Document processed successfully with structure preservation"
            )
            
        finally:
            # Clean up temp file
            print(f"Finished processing file: {request.fileName}")
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks/{media_id}")
async def get_chunks(media_id: str):
    """
    Get all chunks for a specific media file
    """
    try:
        result = supabase.table('chunks').select('*').eq('media_id', media_id).execute()
        
        if not result.data:
            return {"chunks": []}
        
        # Process chunks to include metadata
        processed_chunks = []
        for chunk in result.data:
            chunk_data = {
                "id": chunk["id"],
                "text": chunk["chunk_text"],
                "page_number": chunk["page_number"],
                "metadata": json.loads(chunk["metadata"]) if chunk.get("metadata") else {},
                "embedding": json.loads(chunk["embedding"]) if chunk.get("embedding") else []
            }
            processed_chunks.append(chunk_data)
            
        return {"chunks": processed_chunks}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/media/{media_id}")
async def delete_media(media_id: str):
    """
    Delete a media file and its associated chunks
    """
    try:
        # Get media info
        media_result = supabase.table('media').select('*').eq('id', media_id).single().execute()
        
        if not media_result.data:
            raise HTTPException(status_code=404, detail="Media not found")
            
        # Delete from storage
        storage_path = media_result.data['storage_path']
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([storage_path])
        except Exception as e:
            print(f"Warning: Failed to delete file from storage: {str(e)}")
            
        # Delete chunks
        supabase.table('chunks').delete().eq('media_id', media_id).execute()
        
        # Delete media record
        supabase.table('media').delete().eq('id', media_id).execute()
        
        return {"success": True, "message": "Media and associated data deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 