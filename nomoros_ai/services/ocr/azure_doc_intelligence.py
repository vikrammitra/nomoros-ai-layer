"""
Azure Document Intelligence Service.

This module wraps Azure Document Intelligence (formerly Form Recognizer)
for OCR and layout extraction from PDF documents.

Design notes:
- Uses only the prebuilt-layout model for OCR/layout extraction
- No business logic or risk analysis is performed here
- Designed to be replaceable with another OCR service if needed
"""

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import Optional
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """
    Result from document text extraction.
    
    Attributes:
        success: Whether the extraction was successful
        text_content: The extracted text content
        page_count: Number of pages processed
        error_message: Error message if extraction failed
    """
    success: bool
    text_content: str
    page_count: int
    error_message: Optional[str] = None


class AzureDocumentIntelligenceService:
    """
    Service class for Azure Document Intelligence OCR operations.
    
    This class provides a clean interface for document text extraction
    using Azure's prebuilt-layout model. It is designed to be:
    - Deterministic: Same input produces same output
    - Auditable: Operations can be logged and traced
    - Replaceable: Interface can be implemented by other OCR services
    """
    
    def __init__(self, endpoint: str, api_key: str):
        """
        Initialize the Azure Document Intelligence client.
        
        Args:
            endpoint: Azure Document Intelligence endpoint URL
            api_key: Azure API key for authentication
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self._client: Optional[DocumentAnalysisClient] = None
    
    def _get_client(self) -> DocumentAnalysisClient:
        """
        Get or create the Document Analysis client.
        
        Returns:
            DocumentAnalysisClient instance
        """
        if self._client is None:
            credential = AzureKeyCredential(self.api_key)
            self._client = DocumentAnalysisClient(
                endpoint=self.endpoint,
                credential=credential
            )
        return self._client
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> ExtractionResult:
        """
        Extract text from a PDF document using Azure Document Intelligence.
        
        Uses the prebuilt-layout model which provides:
        - Text extraction with reading order
        - Table structure recognition
        - Selection marks detection
        
        Args:
            pdf_content: Raw PDF file bytes
            
        Returns:
            ExtractionResult with extracted text and metadata
        """
        try:
            client = self._get_client()
            
            # Analyze document using prebuilt-layout model
            # This model extracts text, tables, and structure
            # Note: Some Land Registry PDFs may have page extraction issues
            poller = client.begin_analyze_document(
                model_id="prebuilt-layout",
                document=pdf_content
            )
            
            # Wait for the analysis to complete
            result = poller.result()
            
            # Get page count
            page_count = len(result.pages) if result.pages else 0
            
            # Use result.content for complete text extraction
            # This provides all text in reading order across all pages
            # and is more reliable than iterating through page.lines
            if result.content:
                full_text = result.content
            else:
                # Fallback: Extract text from lines per page
                text_parts = []
                for page_num, page in enumerate(result.pages, 1):
                    page_text_parts = []
                    
                    if page.lines:
                        for line in page.lines:
                            page_text_parts.append(line.content)
                    
                    if page_text_parts:
                        text_parts.append(f"--- Page {page_num} ---")
                        text_parts.extend(page_text_parts)
                
                full_text = "\n".join(text_parts)
            
            return ExtractionResult(
                success=True,
                text_content=full_text,
                page_count=page_count,
                error_message=None
            )
            
        except Exception as e:
            # Return structured error without exposing internal details
            return ExtractionResult(
                success=False,
                text_content="",
                page_count=0,
                error_message=f"Document analysis failed: {str(e)}"
            )
    
    def close(self):
        """
        Close the client connection and release resources.
        """
        if self._client:
            self._client.close()
            self._client = None
