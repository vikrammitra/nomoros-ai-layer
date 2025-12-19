"""
Nomoros AI API - Main Application Entry Point.

This is the main FastAPI application for the Nomoros AI legal
conveyancing document processing backend.

Features:
- Health check endpoint
- Document ingestion with Azure Document Intelligence OCR

To run locally:
    uvicorn nomoros_ai.main:app --host 0.0.0.0 --port 5000 --reload
"""

from fastapi import FastAPI

from nomoros_ai.config import settings, validate_azure_credentials
from nomoros_ai.routers import documents
from nomoros_ai.models.document import HealthResponse


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Legal conveyancing document processing API with Azure Document Intelligence OCR",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include routers
app.include_router(documents.router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns the service status and configuration state.
    Use this endpoint to verify the API is running and
    check if Azure credentials are configured.
    
    Returns:
        HealthResponse with status information
    """
    is_azure_configured, _ = validate_azure_credentials()
    
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        azure_configured=is_azure_configured
    )


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint providing API information.
    
    Returns:
        Basic API information and links to documentation
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Legal conveyancing document processing API",
        "docs": "/docs",
        "health": "/health"
    }
