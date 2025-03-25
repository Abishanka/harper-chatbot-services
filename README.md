# Document Processing API

A FastAPI server that processes documents, extracts text, creates embeddings, and stores them in a Supabase database.

## Features

- Process different document types (PDF, DOCX, images)
- Extract text content (simulated with Docling integration)
- Split text into semantic chunks
- Create embeddings using OpenAI's API
- Store chunks and embeddings in Supabase
- RAG-powered chat with document context

## Getting Started

### Prerequisites

- Python 3.8+
- OpenAI API key
- Supabase account with URL and anon key

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your API keys:
   ```
   cp .env.example .env
   ```
4. Edit the `.env` file with your actual API keys and configuration values

### Running the Server

Start the FastAPI server using Uvicorn:

```
uvicorn app.main:app --reload
```

The server will run at http://localhost:8000 by default.

### API Documentation

Once the server is running, you can access the interactive API documentation at:

- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## API Endpoints

### POST /api/process-chunks

Process a document, extract text, create embeddings, and store in the database.

**Request Body:**
```json
{
  "fileName": "path/to/file.pdf"
}
```

**Response:**
```json
{
  "success": true,
  "chunks": 3,
  "results": [
    {
      "chunkId": "chunk-id-1",
      "pageNumber": 1
    },
    {
      "chunkId": "chunk-id-2",
      "pageNumber": 2
    },
    {
      "chunkId": "chunk-id-3",
      "pageNumber": 3
    }
  ],
  "note": "Integration with Docling would require a separate Python microservice"
}
```

### POST /api/chat

RAG-powered chat endpoint that uses document context to answer user queries.

**Request Body:**
```json
{
  "query": "What does the document say about X?",
  "workspace_id": "workspace-uuid",
  "user_id": "user-id",
  "max_context_chunks": 5
}
```

**Response:**
```json
{
  "answer": "Based on the document, X is described as...",
  "context_sources": [
    {
      "media_id": "media-uuid-1",
      "media_name": "Document1.pdf",
      "chunk_id": "chunk-uuid-1",
      "chunk_text": "X is a concept that...",
      "similarity": 0.92
    },
    {
      "media_id": "media-uuid-2",
      "media_name": "Document2.pdf",
      "chunk_id": "chunk-uuid-2",
      "chunk_text": "Further information about X...",
      "similarity": 0.87
    }
  ]
}
```

## Database Schema

The application expects the following tables in Supabase:

### `media` Table
- `id`: UUID, primary key
- `name`: String, name of the media file
- `media_type`: String, type of media (file, image, etc.)
- `owner_id`: UUID, owner of the media

### `chunks` Table
- `id`: UUID, primary key
- `chunk_text`: String, the text content of the chunk
- `media_id`: UUID, foreign key to media table
- `page_number`: Integer, page number (for files)
- `embedding`: Vector, the embedding representation of the chunk 