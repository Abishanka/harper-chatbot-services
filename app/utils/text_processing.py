import re
from typing import List, Optional
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
import os
import json


def setup_document_converter():
    """
    Set up document converter with advanced processing options
    """
    
    # Create and return converter with options
    return DocumentConverter()


def split_into_chunks(text: str, chunk_size: int = 1000) -> list:
    """
    Split text into chunks using a simple approach.
    
    Args:
        text: The text to split
        chunk_size: Maximum size of each chunk
        
    Returns:
        List of text chunks
    """
    try:
        # Fallback to basic sentence splitting
        chunks = []
        current_chunk = ''
        sentences = text.split('.')
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > chunk_size:
                chunks.append({"text": current_chunk.strip(), "metadata": {}})
                current_chunk = sentence
            else:
                current_chunk += sentence + '.'
        
        if current_chunk:
            chunks.append({"text": current_chunk.strip(), "metadata": {}})
        
        return chunks
        
    except Exception as e:
        print(f"Error in basic chunking: {str(e)}")
        # If all else fails, just create one chunk
        return [{"text": text, "metadata": {}}]


async def process_document_with_docling(file_path: str, file_type: str) -> dict:
    """
    Process document using Docling with simplified features.
    
    Args:
        file_path: Path to the document file
        file_type: Type of the document file
        
    Returns:
        Dictionary containing extracted text and metadata
    """
    try:
        # Set up document converter with advanced options
        converter = setup_document_converter()
        
        # Process the document
        result = converter.convert(file_path)
        doc = result.document
        
        # Extract text content with structure
        content = doc.export_to_markdown()
        
        return {
            "text": content,
            "metadata": {},  # You can add any relevant metadata if needed
            "tables": [],    # No tables to return
            "figures": [],   # No figures to return
            "structure": {"headings": [], "sections": []}  # Simplified structure
        }
        
    except Exception as e:
        print(f"Error processing document with Docling: {str(e)}")
        return {
            "error": f"Failed to process document: {str(e)}",
            "text": "",
            "metadata": {},
            "tables": [],
            "figures": [],
            "structure": {"headings": [], "sections": []}
        }


async def create_embedding(text: str, openai_client) -> list[float]:
    """
    Create an embedding for the given text using OpenAI.
    
    Args:
        text: The text to create an embedding for
        openai_client: OpenAI client instance
        
    Returns:
        List of embedding values
    """
    response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding 


async def background_process_chunks(file_name: str):
    try:
        process_chunk_request = ProcessChunkRequest(fileName=file_name)
        await process_chunks(process_chunk_request)
    except Exception as e:
        print(f"Error in background processing: {str(e)}")
        # Log the error but don't raise it - background task should fail gracefully 