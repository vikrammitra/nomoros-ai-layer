"""
Request models for API endpoints.
"""

from pydantic import BaseModel


class TitleRiskRequest(BaseModel):
    """
    Request model for title risk analysis endpoint.
    
    Attributes:
        ocr_text: The OCR-extracted text from a document
    """
    ocr_text: str
