"""
Document processing router.

Handles document ingestion, OCR extraction, and title risk analysis endpoints.
"""

from fastapi import APIRouter, File, UploadFile, HTTPException

from nomoros_ai.config import settings, validate_azure_credentials
from nomoros_ai.services.ocr.azure_doc_intelligence import (
    AzureDocumentIntelligenceService,
    ExtractionResult
)
from nomoros_ai.services.classify import DocumentClassifier
from nomoros_ai.services.extract.title import TitleExtractor
from nomoros_ai.services.risk.title_rules import TitleRiskAnalyzer
from nomoros_ai.models.document import DocumentIngestionResponse
from nomoros_ai.models.request import TitleRiskRequest
from nomoros_ai.models.title import TitleRiskResponse


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
                error=result.error_message,
                page_count=result.page_count,
                file_size_mb=result.file_size_mb,
                processing_mode=result.processing_mode,
                chunks_processed=result.chunks_processed
            )
        
        # Create text preview (first 500 characters)
        text_preview = result.text_content[:500] if result.text_content else ""
        if len(result.text_content) > 500:
            text_preview += "..."
        
        # Build success message with processing mode info
        if result.processing_mode == "chunked":
            message = f"Successfully extracted text from {result.page_count} page(s) using chunked processing ({result.chunks_processed} chunks)"
        else:
            message = f"Successfully extracted text from {result.page_count} page(s)"
        
        return DocumentIngestionResponse(
            success=True,
            message=message,
            page_count=result.page_count,
            text_preview=text_preview,
            full_text=result.text_content,
            file_size_mb=result.file_size_mb,
            processing_mode=result.processing_mode,
            chunks_processed=result.chunks_processed
        )
        
    finally:
        # Clean up client resources
        ocr_service.close()


@router.post("/title-risk", response_model=TitleRiskResponse)
async def analyze_title_risk(request: TitleRiskRequest) -> TitleRiskResponse:
    """
    Analyze OCR text from a Title Register for risks.
    
    This endpoint:
    1. Classifies the document to confirm it's a Title Register
    2. Extracts structured data (title number, proprietors, restrictions, etc.)
    3. Applies rule-based risk analysis
    4. Returns structured risk assessment suitable for a dashboard
    
    Args:
        request: TitleRiskRequest containing OCR text
        
    Returns:
        TitleRiskResponse with extraction and risk analysis
        
    Raises:
        HTTPException: If document is not a Title Register
    """
    ocr_text = request.ocr_text
    
    if not ocr_text or not ocr_text.strip():
        raise HTTPException(
            status_code=400,
            detail="OCR text is required"
        )
    
    # Step 1: Classify the document
    classifier = DocumentClassifier()
    classification = classifier.classify(ocr_text)
    
    if classification.document_type != "Title Register":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not a Title Register. Detected type: {classification.document_type}"
        )
    
    # Step 2: Extract structured data from the title
    extractor = TitleExtractor()
    extraction = extractor.extract(ocr_text)
    
    # Step 3: Analyze risks using rule-based engine
    risk_analyzer = TitleRiskAnalyzer()
    risk_summary, detailed_risks = risk_analyzer.analyze(extraction)
    
    # Step 4: Build and return response
    return TitleRiskResponse(
        document_type=classification.document_type,
        extraction=extraction,
        risk_summary=risk_summary,
        detailed_risks=detailed_risks
    )
