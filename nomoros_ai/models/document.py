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
        file_size_mb: Size of the uploaded file in megabytes
        processing_mode: "sync" for small files, "chunked" for large files
        chunks_processed: Number of chunks processed (0 for sync mode)
        document_type: Classified document type (e.g., TITLE_REGISTER, LOCAL_AUTHORITY_SEARCH)
        document_type_confidence: Confidence score for classification (0.0-1.0)
        classification_method: Method used for classification (e.g., "rules_v1")
    """
    success: bool
    message: str
    page_count: int = 0
    text_preview: Optional[str] = None
    full_text: Optional[str] = None
    error: Optional[str] = None
    file_size_mb: float = 0.0
    processing_mode: str = "sync"
    chunks_processed: int = 0
    document_type: Optional[str] = None
    document_type_confidence: Optional[float] = None
    classification_method: Optional[str] = None


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
