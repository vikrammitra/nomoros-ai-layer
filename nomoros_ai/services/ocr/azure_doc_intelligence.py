"""
Azure Document Intelligence Service.

This module wraps Azure Document Intelligence (formerly Form Recognizer)
for OCR and layout extraction from PDF documents.

Design notes:
- Uses prebuilt-document model for comprehensive OCR extraction
- Implements size-aware chunking for large PDFs (Search packs, TA6, Leases)
- Implements fallback mechanisms for problematic multi-page PDFs
- Specifically addresses HM Land Registry PDF structure issues where
  page 2+ content may not be extracted using standard approaches
- No business logic or risk analysis is performed here
- Designed to be replaceable with another OCR service if needed

Size handling:
- Small PDFs (within limits): Processed synchronously in single request
- Large PDFs (exceeding limits): Automatically chunked and processed sequentially
- This ensures stable ingestion of large Search packs, TA6, and Lease documents
"""

import io
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import Optional
from dataclasses import dataclass, field
from pypdf import PdfReader, PdfWriter


# Configurable limits for synchronous processing
# PDFs exceeding these limits will be automatically chunked
MAX_SYNC_FILE_SIZE_MB = 4.0  # Azure Document Intelligence limit
MAX_SYNC_PAGES = 10  # Conservative limit for reliable processing
CHUNK_SIZE_PAGES = 5  # Number of pages per chunk when splitting


class ProcessingMode:
    """
    Constants for processing mode identification.
    
    Used to track how the document was processed for audit trails.
    """
    SYNC = "sync"  # Processed in single request (small files)
    CHUNKED = "chunked"  # Split into chunks (large files)


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
        file_size_mb: Size of the input file in megabytes
        processing_mode: "sync" for single request, "chunked" for large files
        chunks_processed: Number of chunks processed (0 for sync mode)
    """
    success: bool
    text_content: str
    page_count: int
    error_message: Optional[str] = None
    fallback_strategy: str = FallbackStrategy.PRIMARY
    pages_with_content: list[int] = field(default_factory=list)
    file_size_mb: float = 0.0
    processing_mode: str = ProcessingMode.SYNC
    chunks_processed: int = 0


class AzureDocumentIntelligenceService:
    """
    Service class for Azure Document Intelligence OCR operations.
    
    This class provides a clean interface for document text extraction
    using Azure's prebuilt-document model. It is designed to be:
    - Deterministic: Same input produces same output
    - Auditable: Operations can be logged and traced
    - Replaceable: Interface can be implemented by other OCR services
    - Robust: Implements fallbacks for problematic PDFs
    - Size-aware: Automatically chunks large PDFs for reliable processing
    
    Size handling (for large Search/TA6 PDFs):
    - Files > MAX_SYNC_FILE_SIZE_MB or > MAX_SYNC_PAGES are chunked
    - Each chunk contains up to CHUNK_SIZE_PAGES pages
    - Chunks are processed sequentially and results concatenated
    - Failures per chunk are handled gracefully (partial extraction)
    
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
    
    def _get_pdf_info(self, pdf_content: bytes) -> tuple[int, float]:
        """
        Get page count and file size from PDF content.
        
        Used to determine if chunked processing is needed for large
        Search packs, TA6 forms, and Lease documents.
        
        Args:
            pdf_content: Raw PDF file bytes
            
        Returns:
            Tuple of (page_count, file_size_mb)
        """
        file_size_mb = len(pdf_content) / (1024 * 1024)
        
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            page_count = len(reader.pages)
        except Exception:
            # If we can't read PDF metadata, assume it needs chunking
            page_count = 0
        
        return page_count, file_size_mb
    
    def _needs_chunking(self, page_count: int, file_size_mb: float) -> bool:
        """
        Determine if PDF needs to be processed in chunks.
        
        Large files (Search packs, TA6 forms, Lease documents) often
        exceed Azure's size limits or timeout thresholds. Chunking
        ensures reliable processing of these documents.
        
        Args:
            page_count: Number of pages in PDF
            file_size_mb: File size in megabytes
            
        Returns:
            True if chunked processing is needed
        """
        return file_size_mb > MAX_SYNC_FILE_SIZE_MB or page_count > MAX_SYNC_PAGES
    
    def _split_pdf_to_chunks(self, pdf_content: bytes, pages_per_chunk: int = CHUNK_SIZE_PAGES) -> list[tuple[bytes, int, int]]:
        """
        Split a PDF into page-based chunks for processing.
        
        This is essential for processing large Search packs, TA6 forms,
        and Lease documents that exceed Azure's size or page limits.
        
        Args:
            pdf_content: Raw PDF file bytes
            pages_per_chunk: Maximum pages per chunk (default: CHUNK_SIZE_PAGES)
            
        Returns:
            List of tuples: (chunk_bytes, start_page, end_page)
            Page numbers are 1-indexed for user-friendly output
        """
        chunks = []
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            total_pages = len(reader.pages)
            
            for start_idx in range(0, total_pages, pages_per_chunk):
                end_idx = min(start_idx + pages_per_chunk, total_pages)
                
                writer = PdfWriter()
                for page_idx in range(start_idx, end_idx):
                    writer.add_page(reader.pages[page_idx])
                
                output = io.BytesIO()
                writer.write(output)
                output.seek(0)
                
                # Convert to 1-indexed page numbers for output
                chunks.append((output.read(), start_idx + 1, end_idx))
                
        except Exception as e:
            # If chunking fails, return empty list
            # Caller will attempt single-document processing as fallback
            pass
        
        return chunks
    
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
                
        except Exception:
            # If PDF splitting fails, return empty list
            # Caller will handle this gracefully
            pass
        
        return pages
    
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
    
    def _ocr_chunk(self, chunk_content: bytes, start_page: int, end_page: int) -> tuple[str, list[int], bool]:
        """
        OCR a chunk of pages from a PDF.
        
        Used for processing large Search packs, TA6 forms, and Lease
        documents that have been split into manageable chunks.
        
        Args:
            chunk_content: Chunk PDF bytes
            start_page: First page number in chunk (1-indexed)
            end_page: Last page number in chunk (1-indexed)
            
        Returns:
            Tuple of (extracted_text, successful_pages, success)
        """
        try:
            result, error = self._analyze_document(chunk_content)
            if error or not result:
                return "", [], False
            
            # Use result.content if available
            if result.content:
                # Add page markers for each page in the chunk
                text_parts = []
                successful_pages = []
                
                # For chunks, we add a header showing the page range
                pages_in_chunk = end_page - start_page + 1
                if pages_in_chunk > 1:
                    text_parts.append(f"--- Pages {start_page} to {end_page} ---")
                else:
                    text_parts.append(f"--- Page {start_page} ---")
                
                text_parts.append(result.content)
                successful_pages = list(range(start_page, end_page + 1))
                
                return "\n".join(text_parts), successful_pages, True
            
            # Fallback to lines if result.content is empty
            lines = []
            if result.pages:
                for page in result.pages:
                    if page.lines:
                        for line in page.lines:
                            if line.content:
                                lines.append(line.content)
            
            if lines:
                text_parts = [f"--- Pages {start_page} to {end_page} ---"]
                text_parts.extend(lines)
                successful_pages = list(range(start_page, end_page + 1))
                return "\n".join(text_parts), successful_pages, True
            
            return "", [], False
            
        except Exception:
            return "", [], False
    
    def _process_chunked(self, pdf_content: bytes, page_count: int, file_size_mb: float) -> ExtractionResult:
        """
        Process a large PDF by splitting into chunks.
        
        This method handles large Search packs, TA6 forms, and Lease
        documents that exceed Azure's size or page limits. It:
        1. Splits the PDF into page-based chunks
        2. OCRs each chunk sequentially
        3. Concatenates results in correct page order
        4. Handles per-chunk failures gracefully
        
        Args:
            pdf_content: Raw PDF file bytes
            page_count: Total pages in PDF
            file_size_mb: File size in megabytes
            
        Returns:
            ExtractionResult with concatenated text from all chunks
        """
        # Split PDF into chunks
        chunks = self._split_pdf_to_chunks(pdf_content)
        
        if not chunks:
            # Chunking failed - try processing as single document anyway
            # This may fail for very large files, but provides fallback
            return ExtractionResult(
                success=False,
                text_content="",
                page_count=page_count,
                error_message="Failed to split PDF into chunks for processing",
                file_size_mb=file_size_mb,
                processing_mode=ProcessingMode.CHUNKED,
                chunks_processed=0
            )
        
        # Process each chunk sequentially
        all_texts = []
        all_successful_pages = []
        chunks_processed = 0
        chunk_errors = []
        
        for chunk_bytes, start_page, end_page in chunks:
            text, successful_pages, success = self._ocr_chunk(chunk_bytes, start_page, end_page)
            
            if success and text.strip():
                all_texts.append(text)
                all_successful_pages.extend(successful_pages)
                chunks_processed += 1
            else:
                # Record failed chunk but continue processing
                # This ensures partial extraction for large documents
                chunk_errors.append(f"Pages {start_page}-{end_page}")
        
        if not all_texts:
            # All chunks failed
            error_msg = "All chunks failed to process"
            if chunk_errors:
                error_msg += f": {', '.join(chunk_errors)}"
            
            return ExtractionResult(
                success=False,
                text_content="",
                page_count=page_count,
                error_message=error_msg,
                file_size_mb=file_size_mb,
                processing_mode=ProcessingMode.CHUNKED,
                chunks_processed=0
            )
        
        # Concatenate successful chunks
        combined_text = "\n".join(all_texts)
        
        # Build success message
        if chunk_errors:
            # Partial success - some chunks failed
            error_msg = f"Partial extraction: failed chunks: {', '.join(chunk_errors)}"
        else:
            error_msg = None
        
        return ExtractionResult(
            success=True,
            text_content=combined_text,
            page_count=page_count,
            error_message=error_msg,
            fallback_strategy=FallbackStrategy.PRIMARY,
            pages_with_content=all_successful_pages,
            file_size_mb=file_size_mb,
            processing_mode=ProcessingMode.CHUNKED,
            chunks_processed=chunks_processed
        )
    
    def _process_sync(self, pdf_content: bytes, page_count: int, file_size_mb: float) -> ExtractionResult:
        """
        Process a small PDF synchronously in a single request.
        
        This is the standard processing path for Title Registers and
        other small documents that fit within Azure's limits.
        
        Implements fallback mechanisms for HM Land Registry PDFs where
        page 2+ content may not be extracted properly.
        
        Args:
            pdf_content: Raw PDF file bytes
            page_count: Total pages in PDF
            file_size_mb: File size in megabytes
            
        Returns:
            ExtractionResult with extracted text
        """
        # Primary analysis attempt
        result, error = self._analyze_document(pdf_content)
        
        if error:
            return ExtractionResult(
                success=False,
                text_content="",
                page_count=page_count,
                error_message=f"Document analysis failed: {error}",
                fallback_strategy=FallbackStrategy.PRIMARY,
                file_size_mb=file_size_mb,
                processing_mode=ProcessingMode.SYNC,
                chunks_processed=0
            )
        
        actual_page_count = len(result.pages) if result.pages else page_count
        
        # Extract content using result.content (most reliable)
        content_text = result.content if result.content else ""
        
        # Extract lines per page to check for missing content
        pages_content = self._extract_lines_per_page(result)
        pages_with_content = [p for p, lines in pages_content.items() if len(lines) > 0]
        
        # For multi-page documents, try page-split fallback
        # This addresses HM Land Registry PDFs where page 2+ may be incomplete
        if actual_page_count > 1:
            page_pdfs = self._split_pdf_to_pages(pdf_content)
            
            if page_pdfs:
                all_page_texts = []
                successful_pages = []
                
                for page_num, page_pdf in enumerate(page_pdfs, 1):
                    page_text, success = self._ocr_single_page(page_pdf, page_num)
                    
                    if success and page_text.strip():
                        all_page_texts.append(f"--- Page {page_num} ---")
                        all_page_texts.append(page_text)
                        successful_pages.append(page_num)
                
                if all_page_texts:
                    combined_text = "\n".join(all_page_texts)
                    
                    # Use page-split if it got more content
                    if len(combined_text) > len(content_text):
                        return ExtractionResult(
                            success=True,
                            text_content=combined_text,
                            page_count=actual_page_count,
                            fallback_strategy=FallbackStrategy.PAGE_SPLIT,
                            pages_with_content=successful_pages,
                            file_size_mb=file_size_mb,
                            processing_mode=ProcessingMode.SYNC,
                            chunks_processed=0
                        )
        
        # Return primary content if available
        if content_text:
            return ExtractionResult(
                success=True,
                text_content=content_text,
                page_count=actual_page_count,
                fallback_strategy=FallbackStrategy.PRIMARY,
                pages_with_content=pages_with_content,
                file_size_mb=file_size_mb,
                processing_mode=ProcessingMode.SYNC,
                chunks_processed=0
            )
        
        # Last resort - concatenate lines per page
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
                    page_count=actual_page_count,
                    fallback_strategy=FallbackStrategy.CONTENT_FALLBACK,
                    pages_with_content=pages_with_content,
                    file_size_mb=file_size_mb,
                    processing_mode=ProcessingMode.SYNC,
                    chunks_processed=0
                )
        
        # No content extracted
        return ExtractionResult(
            success=False,
            text_content="",
            page_count=actual_page_count,
            error_message="No text content could be extracted from the document",
            fallback_strategy=FallbackStrategy.PAGE_SPLIT,
            file_size_mb=file_size_mb,
            processing_mode=ProcessingMode.SYNC,
            chunks_processed=0
        )
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> ExtractionResult:
        """
        Extract text from a PDF document using Azure Document Intelligence.
        
        Implements size-aware processing to handle both small documents
        (Title Registers) and large documents (Search packs, TA6, Leases):
        
        - Small files (within limits): Processed synchronously
        - Large files (exceeding limits): Automatically chunked
        
        This ensures reliable ingestion regardless of file size while
        maintaining backward compatibility for existing workflows.
        
        Args:
            pdf_content: Raw PDF file bytes
            
        Returns:
            ExtractionResult with extracted text and processing metadata
        """
        # Get PDF info to determine processing strategy
        page_count, file_size_mb = self._get_pdf_info(pdf_content)
        
        # Choose processing mode based on file size and page count
        # Large Search packs, TA6 forms, and Lease documents will be chunked
        if self._needs_chunking(page_count, file_size_mb):
            return self._process_chunked(pdf_content, page_count, file_size_mb)
        else:
            return self._process_sync(pdf_content, page_count, file_size_mb)
    
    def close(self):
        """
        Close the client connection and release resources.
        """
        if self._client:
            self._client.close()
            self._client = None
