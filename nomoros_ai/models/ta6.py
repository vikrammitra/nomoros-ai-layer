"""
TA6 Property Information Form models.

Pydantic models for structured extraction of TA6 seller disclosures.
These forms are completed by sellers in UK residential conveyancing and
contain critical property information for buyers.

IMPORTANT:
- These models capture FACTUAL disclosures only
- No risk assessment or legal conclusions
- All risk decisions are made in the deterministic rules layer
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A quote from the document that supports an extracted answer."""
    ref: Optional[str] = Field(None, description="Reference number or section from the form")
    quote: str = Field(..., description="Direct quote from document (max 25 words)")
    char_start: int = Field(..., description="Character offset where quote starts")
    char_end: int = Field(..., description="Character offset where quote ends")


class TA6Question(BaseModel):
    """A single question and answer from the TA6 form."""
    question_id: Optional[str] = Field(None, description="Question number (e.g., '1.1', '2.3')")
    question_text: str = Field(..., description="The question as stated in the form")
    answer_normalised: Literal[
        "yes", "no", "unknown", "not_applicable", "details_provided"
    ] = Field(..., description="Standardised answer value")
    answer_raw: Optional[str] = Field(None, description="Raw answer text from form")
    details: Optional[str] = Field(None, description="Additional details if provided")
    answer_status: Literal[
        "clear", "unclear", "missing", "contradictory"
    ] = Field("clear", description="Quality of the answer")
    clarification_question: Optional[str] = Field(
        None, description="Suggested follow-up question if answer is unclear"
    )
    evidence: List[Evidence] = Field(
        default_factory=list, description="Supporting quotes from the document"
    )


class TA6Section(BaseModel):
    """A section of the TA6 form containing related questions."""
    section_name: str = Field(..., description="Section title (e.g., 'Boundaries', 'Disputes')")
    questions: List[TA6Question] = Field(default_factory=list)


class TA6Contradiction(BaseModel):
    """A detected contradiction within the TA6 form."""
    type: str = Field(..., description="Type of contradiction (e.g., 'answer_conflict', 'missing_attachment')")
    description: str = Field(..., description="Human-readable description of the contradiction")
    items: List[dict] = Field(default_factory=list, description="Items involved in the contradiction")


class TA6FollowUp(BaseModel):
    """A recommended follow-up question for the seller."""
    priority: Literal["high", "medium", "low"] = Field(..., description="Urgency of the follow-up")
    question: str = Field(..., description="The question to ask")
    reason: Literal[
        "missing", "unclear", "contradiction", "attachment_referenced"
    ] = Field(..., description="Why this follow-up is needed")


class TA6DocumentMeta(BaseModel):
    """Metadata about the TA6 form itself."""
    property_address: Optional[str] = Field(None, description="Property address from the form")
    seller_names: List[str] = Field(default_factory=list, description="Names of sellers")
    form_date: Optional[str] = Field(None, description="Date the form was completed")
    form_version: Optional[str] = Field(None, description="TA6 form version (e.g., '5th edition')")


class TA6ExtractionResult(BaseModel):
    """Complete extraction result for a TA6 Property Information Form."""
    is_ta6: bool = Field(True, description="Whether the document is a TA6 form")
    document_meta: TA6DocumentMeta = Field(default_factory=lambda: TA6DocumentMeta())
    sections: List[TA6Section] = Field(default_factory=list)
    contradictions: List[TA6Contradiction] = Field(default_factory=list)
    missing_or_referenced_attachments: List[dict] = Field(
        default_factory=list,
        description="Attachments mentioned but not provided"
    )
    follow_up_questions: List[TA6FollowUp] = Field(default_factory=list)


class TA6ChunkExtraction(BaseModel):
    """Partial extraction from a single chunk (used in map phase)."""
    is_ta6: bool = Field(True, description="Whether this chunk contains TA6 content")
    sections: List[TA6Section] = Field(default_factory=list)
    contradictions: List[TA6Contradiction] = Field(default_factory=list)
    missing_or_referenced_attachments: List[dict] = Field(default_factory=list)
    follow_up_questions: List[TA6FollowUp] = Field(default_factory=list)
    document_meta: Optional[TA6DocumentMeta] = Field(None)


class TA6TextChunk(BaseModel):
    """A chunk of TA6 text with offset tracking."""
    chunk_id: int = Field(..., description="Sequential chunk identifier")
    text: str = Field(..., description="Chunk text content")
    char_start: int = Field(..., description="Start offset in original text")
    char_end: int = Field(..., description="End offset in original text")


class TA6ParseRequest(BaseModel):
    """Request model for TA6 parsing endpoint."""
    ocr_text: str = Field(..., description="Full OCR text from the TA6 document")


class TA6ParseResponse(BaseModel):
    """Response model for TA6 parsing endpoint."""
    success: bool
    message: str
    status: Literal["PARSED_TA6", "FAILED", "NOT_TA6"]
    document_type: str = "TA6"
    ta6_extraction: Optional[TA6ExtractionResult] = None
    risk_summary: Optional[dict] = None
    detailed_risks: Optional[List[dict]] = None
    parser_version: str = "ta6_parser_v1"
    chunks_processed: int = 0
    error: Optional[str] = None
