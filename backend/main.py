from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
from app.models.database import engine, Base
from app.api import emails_router, search_router, sync_router, analytics_router, labels_router, test_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Gmail Backup & Management System",
    description="A comprehensive application for backing up and managing Gmail emails with AI-powered analysis",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(emails_router, prefix="/api/v1/emails", tags=["emails"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(labels_router, prefix="/api/v1/labels", tags=["labels"])
app.include_router(test_router, prefix="/api/v1/test", tags=["test"])

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Gmail Backup & Management System API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "emails": "/api/v1/emails",
            "search": "/api/v1/search",
            "sync": "/api/v1/sync",
            "analytics": "/api/v1/analytics",
            "test": "/api/v1/test"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Gmail Backup & Management System",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
