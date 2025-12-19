"""
Document models for API request/response handling.

These Pydantic models define the structure for document ingestion
endpoints and their responses.
"""

from pydantic import BaseModel
from typing import Optional


class DocumentIngestionResponse(BaseModel):
    """
    Response model for document ingestion endpoint.
    
    Attributes:
        success: Whether the document was processed successfully
        message: Human-readable status message
        page_count: Number of pages extracted from the document
        text_preview: Preview of extracted text (first 500 characters)
        full_text: Complete extracted text (optional, can be large)
        error: Error message if processing failed
    """
    success: bool
    message: str
    page_count: int = 0
    text_preview: Optional[str] = None
    full_text: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint.
    
    Attributes:
        status: Service health status
        version: API version
        azure_configured: Whether Azure credentials are configured
    """
    status: str
    version: str
    azure_configured: bool
