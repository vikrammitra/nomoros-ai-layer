"""
Azure Document Intelligence Service.

This module wraps Azure Document Intelligence (formerly Form Recognizer)
for OCR and layout extraction from PDF documents.

Design notes:
- Uses prebuilt-document model for comprehensive OCR extraction
- Implements fallback mechanisms for problematic multi-page PDFs
- Specifically addresses HM Land Registry PDF structure issues where
  page 2+ content may not be extracted using standard approaches
- No business logic or risk analysis is performed here
- Designed to be replaceable with another OCR service if needed
"""

import io
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import Optional
from dataclasses import dataclass, field
from pypdf import PdfReader, PdfWriter


class FallbackStrategy:
    """
    Constants for fallback strategy identification.
    
    Used to track which extraction method was successful,
    enabling audit trails and debugging of OCR issues.
    """
    PRIMARY = "primary"  # Standard extraction worked
    CONTENT_FALLBACK = "content_fallback"  # Used result.content
    PAGE_SPLIT = "page_split"  # Split PDF and OCR'd pages individually


@dataclass
class ExtractionResult:
    """
    Result from document text extraction.
    
    Attributes:
        success: Whether the extraction was successful
        text_content: The extracted text content
        page_count: Number of pages processed
        error_message: Error message if extraction failed
        fallback_strategy: Which extraction strategy was used
        pages_with_content: List of page numbers that had content
    """
    success: bool
    text_content: str
    page_count: int
    error_message: Optional[str] = None
    fallback_strategy: str = FallbackStrategy.PRIMARY
    pages_with_content: list[int] = field(default_factory=list)


class AzureDocumentIntelligenceService:
    """
    Service class for Azure Document Intelligence OCR operations.
    
    This class provides a clean interface for document text extraction
    using Azure's prebuilt-document model. It is designed to be:
    - Deterministic: Same input produces same output
    - Auditable: Operations can be logged and traced
    - Replaceable: Interface can be implemented by other OCR services
    - Robust: Implements fallbacks for problematic PDFs
    
    Fallback mechanism (addresses HM Land Registry multi-page PDF issues):
    1. Primary: Use prebuilt-document model
    2. Content fallback: Use result.content if page lines are incomplete
    3. Page-split fallback: Split PDF and OCR each page separately
    """
    
    # Model to use for OCR - prebuilt-document is more comprehensive
    # than prebuilt-layout for legal documents
    MODEL_ID = "prebuilt-document"
    
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
    
    def _analyze_document(self, pdf_content: bytes) -> tuple:
        """
        Perform Azure Document Intelligence analysis on PDF content.
        
        Args:
            pdf_content: Raw PDF file bytes
            
        Returns:
            Tuple of (result, error_message)
        """
        try:
            client = self._get_client()
            poller = client.begin_analyze_document(
                model_id=self.MODEL_ID,
                document=pdf_content
            )
            result = poller.result()
            return result, None
        except Exception as e:
            return None, str(e)
    
    def _extract_lines_per_page(self, result) -> dict[int, list[str]]:
        """
        Extract text lines organized by page number.
        
        Args:
            result: Azure analysis result
            
        Returns:
            Dictionary mapping page number to list of text lines
        """
        pages_content: dict[int, list[str]] = {}
        
        if result.pages:
            for page_num, page in enumerate(result.pages, 1):
                lines = []
                if page.lines:
                    for line in page.lines:
                        if line.content:
                            lines.append(line.content)
                pages_content[page_num] = lines
        
        return pages_content
    
    def _check_missing_pages(self, pages_content: dict[int, list[str]], expected_pages: int) -> list[int]:
        """
        Identify pages that have zero extracted lines.
        
        This addresses HM Land Registry PDF structure issues where
        certain pages (often page 2+) fail to extract content.
        
        Args:
            pages_content: Dictionary of page number to lines
            expected_pages: Total number of pages in document
            
        Returns:
            List of page numbers with no content
        """
        missing = []
        for page_num in range(1, expected_pages + 1):
            if page_num not in pages_content or len(pages_content[page_num]) == 0:
                missing.append(page_num)
        return missing
    
    def _split_pdf_to_pages(self, pdf_content: bytes) -> list[bytes]:
        """
        Split a multi-page PDF into individual single-page PDFs.
        
        Uses pypdf to extract each page as a separate PDF document.
        This enables per-page OCR when the combined document fails.
        
        Args:
            pdf_content: Raw PDF file bytes
            
        Returns:
            List of single-page PDF bytes
        """
        pages = []
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            
            for page_num in range(len(reader.pages)):
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num])
                
                output = io.BytesIO()
                writer.write(output)
                output.seek(0)
                pages.append(output.read())
                
        except Exception as e:
            # If PDF splitting fails, return empty list
            # Caller will handle this gracefully
            pass
        
        return pages
    
    def _ocr_single_page(self, page_content: bytes, page_num: int) -> tuple[str, bool]:
        """
        OCR a single page PDF.
        
        Args:
            page_content: Single page PDF bytes
            page_num: Page number for labeling
            
        Returns:
            Tuple of (extracted_text, success)
        """
        try:
            result, error = self._analyze_document(page_content)
            if error or not result:
                return "", False
            
            # Use result.content for single page
            if result.content:
                return result.content, True
            
            # Fallback to lines
            lines = []
            if result.pages:
                for page in result.pages:
                    if page.lines:
                        for line in page.lines:
                            if line.content:
                                lines.append(line.content)
            
            return "\n".join(lines), len(lines) > 0
            
        except Exception:
            return "", False
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> ExtractionResult:
        """
        Extract text from a PDF document using Azure Document Intelligence.
        
        Implements a robust fallback mechanism to handle problematic PDFs,
        specifically addressing HM Land Registry multi-page PDF structure issues
        where page 2+ content may not be extracted using standard approaches.
        
        Fallback order:
        1. Primary: Analyze with prebuilt-document, use result.content
        2. Content fallback: Combine result.content with page lines
        3. Page-split fallback: Split PDF and OCR each page separately
        
        Args:
            pdf_content: Raw PDF file bytes
            
        Returns:
            ExtractionResult with extracted text, metadata, and fallback info
        """
        # Step 1: Primary analysis attempt
        result, error = self._analyze_document(pdf_content)
        
        if error:
            return ExtractionResult(
                success=False,
                text_content="",
                page_count=0,
                error_message=f"Document analysis failed: {error}",
                fallback_strategy=FallbackStrategy.PRIMARY
            )
        
        page_count = len(result.pages) if result.pages else 0
        
        # Step 2: Extract content using result.content (most reliable)
        # This is the content fallback - always prefer result.content
        if result.content:
            content_text = result.content
        else:
            content_text = ""
        
        # Step 3: Also extract lines per page to check for missing content
        pages_content = self._extract_lines_per_page(result)
        pages_with_content = [p for p, lines in pages_content.items() if len(lines) > 0]
        
        # Step 4: For multi-page documents, ALWAYS try page-split fallback
        # This addresses HM Land Registry PDFs where page 2+ content may be
        # partially extracted (Azure reports lines but misses sections)
        # We compare primary vs page-split and use whichever has more content
        if page_count > 1:
            # Try splitting the PDF and OCR'ing each page separately
            page_pdfs = self._split_pdf_to_pages(pdf_content)
            
            if len(page_pdfs) > 0:
                all_page_texts = []
                successful_pages = []
                
                for page_num, page_pdf in enumerate(page_pdfs, 1):
                    page_text, success = self._ocr_single_page(page_pdf, page_num)
                    
                    if success and page_text.strip():
                        all_page_texts.append(f"--- Page {page_num} ---")
                        all_page_texts.append(page_text)
                        successful_pages.append(page_num)
                
                if len(all_page_texts) > 0:
                    combined_text = "\n".join(all_page_texts)
                    
                    # Check if page-split got more content than primary
                    if len(combined_text) > len(content_text):
                        return ExtractionResult(
                            success=True,
                            text_content=combined_text,
                            page_count=len(page_pdfs),
                            fallback_strategy=FallbackStrategy.PAGE_SPLIT,
                            pages_with_content=successful_pages
                        )
        
        # Step 5: Return primary content if available
        # For single-page documents or when page-split didn't yield more content
        if content_text:
            # Single page = PRIMARY, multi-page where we tried fallback but
            # primary had more content = also PRIMARY (no fallback was used)
            return ExtractionResult(
                success=True,
                text_content=content_text,
                page_count=page_count,
                fallback_strategy=FallbackStrategy.PRIMARY,
                pages_with_content=pages_with_content
            )
        
        # Step 7: Last resort - concatenate whatever lines we got per page
        if pages_content:
            text_parts = []
            for page_num in sorted(pages_content.keys()):
                if pages_content[page_num]:
                    text_parts.append(f"--- Page {page_num} ---")
                    text_parts.extend(pages_content[page_num])
            
            if text_parts:
                return ExtractionResult(
                    success=True,
                    text_content="\n".join(text_parts),
                    page_count=page_count,
                    fallback_strategy=FallbackStrategy.CONTENT_FALLBACK,
                    pages_with_content=pages_with_content
                )
        
        # No content extracted at all
        return ExtractionResult(
            success=False,
            text_content="",
            page_count=page_count,
            error_message="No text content could be extracted from the document",
            fallback_strategy=FallbackStrategy.PAGE_SPLIT
        )
    
    def close(self):
        """
        Close the client connection and release resources.
        """
        if self._client:
            self._client.close()
            self._client = None
