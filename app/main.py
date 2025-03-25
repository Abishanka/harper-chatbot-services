from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routes
from app.routes.process_chunks import router as process_chunks_router
from app.routes.chat import router as chat_router
from app.routes.embeddings import router as embeddings_router

# Create FastAPI app
app = FastAPI(
    title="Document Processing API",
    description="API for processing documents and creating embeddings",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(process_chunks_router, prefix="/api", tags=["Document Processing"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(embeddings_router, prefix="/api/embeddings", tags=["Embeddings"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Document Processing API is running",
        "docs": "/docs",
        "version": "1.0.0"
    } 