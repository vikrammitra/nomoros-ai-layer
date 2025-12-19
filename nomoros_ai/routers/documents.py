"""
Document processing router.

Handles document ingestion and OCR extraction endpoints.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException

from nomoros_ai.config import settings, validate_azure_credentials
from nomoros_ai.services.ocr.azure_doc_intelligence import (
    AzureDocumentIntelligenceService,
    ExtractionResult
)
from nomoros_ai.models.document import DocumentIngestionResponse


router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/ingest", response_model=DocumentIngestionResponse)
async def ingest_document(file: UploadFile = File(...)) -> DocumentIngestionResponse:
    """
    Ingest a PDF document and extract text using Azure Document Intelligence.
    
    This endpoint:
    1. Validates that Azure credentials are configured
    2. Validates that the uploaded file is a PDF
    3. Sends the PDF to Azure Document Intelligence for OCR
    4. Returns the extracted text content
    
    Args:
        file: Uploaded PDF file
        
    Returns:
        DocumentIngestionResponse with extracted text and metadata
        
    Raises:
        HTTPException: If Azure credentials are missing or file is invalid
    """
    # Validate Azure credentials are configured
    is_valid, error_msg = validate_azure_credentials()
    if not is_valid:
        raise HTTPException(
            status_code=503,
            detail=f"Azure Document Intelligence is not configured: {error_msg}"
        )
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file."
        )
    
    # Validate content type if provided
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type: {file.content_type}. Expected application/pdf"
        )
    
    # Read file content
    try:
        pdf_content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file: {str(e)}"
        )
    
    # Validate file is not empty
    if len(pdf_content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )
    
    # Initialize Azure Document Intelligence service
    # We've validated credentials above, so these are guaranteed to be set
    assert settings.azure_document_intelligence_endpoint is not None
    assert settings.azure_document_intelligence_key is not None
    
    ocr_service = AzureDocumentIntelligenceService(
        endpoint=settings.azure_document_intelligence_endpoint,
        api_key=settings.azure_document_intelligence_key
    )
    
    try:
        # Extract text from PDF
        result: ExtractionResult = ocr_service.extract_text_from_pdf(pdf_content)
        
        if not result.success:
            return DocumentIngestionResponse(
                success=False,
                message="Document processing failed",
                error=result.error_message
            )
        
        # Create text preview (first 500 characters)
        text_preview = result.text_content[:500] if result.text_content else ""
        if len(result.text_content) > 500:
            text_preview += "..."
        
        return DocumentIngestionResponse(
            success=True,
            message=f"Successfully extracted text from {result.page_count} page(s)",
            page_count=result.page_count,
            text_preview=text_preview,
            full_text=result.text_content
        )
        
    finally:
        # Clean up client resources
        ocr_service.close()
