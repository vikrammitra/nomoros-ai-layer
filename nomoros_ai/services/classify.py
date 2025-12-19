"""
Document classification service.

Provides deterministic classification of legal documents based on
structural patterns and keywords. No ML/LLM used here.

Design notes:
- Uses simple heuristics for reliable classification
- Designed to be extended with additional document types
- Returns confidence scores based on matching criteria
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassificationResult:
    """
    Result of document classification.
    
    Attributes:
        document_type: Identified document type
        confidence: Confidence score (0.0-1.0)
        matched_indicators: List of indicators that matched
    """
    document_type: str
    confidence: float
    matched_indicators: list[str]


class DocumentClassifier:
    """
    Classifier for legal conveyancing documents.
    
    Uses deterministic heuristics to identify document types.
    Currently supports:
    - HM Land Registry Title Register
    
    Can be extended to support:
    - Title Plans
    - Leases
    - Transfer deeds
    - etc.
    """
    
    # Indicators for Title Register documents
    # These are structural elements that appear in genuine Land Registry registers
    TITLE_REGISTER_INDICATORS = [
        # Primary indicators (strong signal)
        ("Title number", 0.3),
        ("Edition date", 0.2),
        ("Property Register", 0.2),
        ("Proprietorship Register", 0.2),
        ("Charges Register", 0.1),
        
        # Secondary indicators (supporting signal)
        ("HM Land Registry", 0.1),
        ("Official copy", 0.1),
        ("register of title", 0.1),
        ("Land Registration Act", 0.1),
    ]
    
    # Minimum confidence threshold to classify as Title Register
    TITLE_REGISTER_THRESHOLD = 0.5
    
    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a document based on its extracted text.
        
        Args:
            text: OCR-extracted text from the document
            
        Returns:
            ClassificationResult with document type and confidence
        """
        # Check for Title Register indicators
        title_register_result = self._check_title_register(text)
        
        if title_register_result.confidence >= self.TITLE_REGISTER_THRESHOLD:
            return title_register_result
        
        # Default to unknown document type
        return ClassificationResult(
            document_type="Unknown",
            confidence=0.0,
            matched_indicators=[]
        )
    
    def _check_title_register(self, text: str) -> ClassificationResult:
        """
        Check if document is a Title Register.
        
        Uses weighted indicators to calculate confidence score.
        Higher weights are given to section headings that are
        unique to Title Registers.
        
        Args:
            text: Document text to analyze
            
        Returns:
            ClassificationResult for Title Register classification
        """
        text_upper = text.upper()
        total_score = 0.0
        matched = []
        
        for indicator, weight in self.TITLE_REGISTER_INDICATORS:
            if indicator.upper() in text_upper:
                total_score += weight
                matched.append(indicator)
        
        # Cap confidence at 1.0
        confidence = min(total_score, 1.0)
        
        return ClassificationResult(
            document_type="Title Register" if confidence >= self.TITLE_REGISTER_THRESHOLD else "Unknown",
            confidence=confidence,
            matched_indicators=matched
        )
    
    def is_title_register(self, text: str) -> bool:
        """
        Quick check if document is a Title Register.
        
        Args:
            text: Document text to analyze
            
        Returns:
            True if document is classified as Title Register
        """
        result = self.classify(text)
        return result.document_type == "Title Register"
