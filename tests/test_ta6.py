"""
Tests for TA6 Property Information Form parsing pipeline.

Tests cover:
1. TA6 chunker with header removal and overlap
2. TA6 extraction models
3. Negative case: Non-TA6 document
"""

import pytest
from nomoros_ai.models.ta6 import (
    Evidence,
    TA6Question,
    TA6Section,
    TA6ExtractionResult,
    TA6ChunkExtraction,
    TA6TextChunk,
    TA6ParseRequest,
    TA6ParseResponse,
    TA6DocumentMeta,
    TA6Contradiction,
    TA6FollowUp,
)
from nomoros_ai.services.chunking.ta6_chunker import TA6Chunker


class TestTA6Chunker:
    """Tests for the TA6-specific text chunker."""
    
    def test_empty_text_returns_empty_list(self):
        """Empty or whitespace text should return no chunks."""
        chunker = TA6Chunker()
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []
        assert chunker.chunk_text("\n\n") == []
    
    def test_short_text_single_chunk(self):
        """Short text should result in a single chunk."""
        chunker = TA6Chunker()
        text = "1.1 Have you received any complaints about the property?\nNo"
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0].chunk_id == 0
        assert "complaints" in chunks[0].text
    
    def test_header_removal(self):
        """TA6 headers and footers should be removed."""
        chunker = TA6Chunker()
        text = """Law Society TA6 (5th edition)
        
1.1 Have you received any complaints about the property?
No

Page 1 of 10

Seller's Property Information Form (5th edition)

1.2 Is the property subject to any disputes?
Yes - ongoing boundary dispute with neighbour

Copyright 2020 Law Society
"""
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) >= 1
        combined_text = " ".join(c.text for c in chunks)
        assert "Law Society TA6 (5th edition)" not in combined_text
        assert "Page 1 of 10" not in combined_text
        assert "Copyright" not in combined_text
        assert "complaints" in combined_text
        assert "boundary dispute" in combined_text
    
    def test_checkbox_noise_removal(self):
        """Checkbox artifacts should be cleaned."""
        chunker = TA6Chunker()
        text = "1.1 Have you received complaints? [X] Yes [ ] No"
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert "[X]" not in chunks[0].text
        assert "[ ]" not in chunks[0].text
    
    def test_multiple_chunks_with_overlap(self):
        """Large text should be split into overlapping chunks."""
        chunker = TA6Chunker(chunk_size=500, overlap=100)
        
        long_text = "\n".join([
            f"{i}. Question number {i}: This is a sample question with enough text to test chunking."
            for i in range(1, 50)
        ])
        
        chunks = chunker.chunk_text(long_text)
        
        assert len(chunks) > 1
        
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == i
            assert len(chunk.text) > 0
            assert chunk.char_start >= 0
            assert chunk.char_end > chunk.char_start
    
    def test_offset_tracking(self):
        """Chunk offsets should map back to original text."""
        chunker = TA6Chunker(chunk_size=100, overlap=20)
        text = "Section 1: Boundaries\n1.1 Who owns the boundary fences?\nThe property owner owns all boundary fences as shown on the attached plan."
        
        chunks = chunker.chunk_text(text)
        
        assert all(chunk.char_start >= 0 for chunk in chunks)
        assert all(chunk.char_end <= len(text) + 10 for chunk in chunks)


class TestTA6Models:
    """Tests for TA6 Pydantic models."""
    
    def test_evidence_model(self):
        """Evidence model should capture document quotes."""
        evidence = Evidence(
            ref="1.1",
            quote="No complaints received",
            char_start=100,
            char_end=122
        )
        assert evidence.ref == "1.1"
        assert evidence.quote == "No complaints received"
    
    def test_ta6_question_model(self):
        """TA6Question should capture question and answer details."""
        question = TA6Question(
            question_id="1.1",
            question_text="Have you received any complaints about the property?",
            answer_normalised="no",
            answer_raw="No",
            answer_status="clear",
            evidence=[]
        )
        assert question.question_id == "1.1"
        assert question.answer_normalised == "no"
        assert question.answer_status == "clear"
    
    def test_ta6_question_with_unclear_answer(self):
        """Questions can have unclear status with follow-up."""
        question = TA6Question(
            question_id="2.1",
            question_text="Are there any disputes about the property?",
            answer_normalised="details_provided",
            answer_raw="See attached",
            answer_status="unclear",
            clarification_question="Please provide specific details of any disputes",
            evidence=[]
        )
        assert question.answer_status == "unclear"
        assert question.clarification_question is not None
    
    def test_ta6_section_model(self):
        """TA6Section should contain questions."""
        section = TA6Section(
            section_name="Boundaries",
            questions=[
                TA6Question(
                    question_id="1.1",
                    question_text="Who owns the boundaries?",
                    answer_normalised="details_provided",
                    evidence=[]
                )
            ]
        )
        assert section.section_name == "Boundaries"
        assert len(section.questions) == 1
    
    def test_ta6_extraction_result_defaults(self):
        """TA6ExtractionResult should have sensible defaults."""
        result = TA6ExtractionResult()
        
        assert result.is_ta6 is True
        assert result.sections == []
        assert result.contradictions == []
        assert result.follow_up_questions == []
    
    def test_ta6_document_meta(self):
        """Document metadata should capture form details."""
        meta = TA6DocumentMeta(
            property_address="123 Test Street, London",
            seller_names=["John Smith", "Jane Smith"],
            form_date="2024-01-15",
            form_version="5th edition"
        )
        assert meta.property_address == "123 Test Street, London"
        assert len(meta.seller_names) == 2
    
    def test_ta6_contradiction_model(self):
        """Contradiction model should capture conflicts."""
        contradiction = TA6Contradiction(
            type="answer_conflict",
            description="Section 1.1 says Yes but Section 3.2 says No",
            items=[{"section": "1.1", "answer": "yes"}, {"section": "3.2", "answer": "no"}]
        )
        assert contradiction.type == "answer_conflict"
        assert len(contradiction.items) == 2
    
    def test_ta6_follow_up_model(self):
        """Follow-up questions should have priority."""
        follow_up = TA6FollowUp(
            priority="high",
            question="Please clarify the boundary dispute status",
            reason="contradiction"
        )
        assert follow_up.priority == "high"
        assert follow_up.reason == "contradiction"
    
    def test_ta6_parse_response_success(self):
        """Parse response should handle success case."""
        response = TA6ParseResponse(
            success=True,
            message="Successfully extracted TA6 data",
            status="PARSED_TA6",
            ta6_extraction=TA6ExtractionResult(),
            chunks_processed=5
        )
        assert response.success is True
        assert response.status == "PARSED_TA6"
    
    def test_ta6_parse_response_failure(self):
        """Parse response should handle failure case."""
        response = TA6ParseResponse(
            success=False,
            message="Parsing failed",
            status="FAILED",
            error="Azure OpenAI not configured"
        )
        assert response.success is False
        assert response.status == "FAILED"
        assert response.error is not None


class TestTA6NegativeCase:
    """Tests for non-TA6 document handling."""
    
    def test_chunk_extraction_not_ta6(self):
        """Chunk extraction can indicate non-TA6 content."""
        chunk = TA6ChunkExtraction(is_ta6=False, document_meta=None)
        assert chunk.is_ta6 is False
        assert chunk.sections == []
    
    def test_extraction_result_not_ta6(self):
        """Extraction result can indicate document is not TA6."""
        result = TA6ExtractionResult(is_ta6=False)
        assert result.is_ta6 is False


class TestTA6RequestResponse:
    """Tests for API request/response models."""
    
    def test_parse_request_model(self):
        """Parse request requires OCR text."""
        request = TA6ParseRequest(ocr_text="Sample TA6 text")
        assert request.ocr_text == "Sample TA6 text"
    
    def test_ta6_text_chunk_model(self):
        """Text chunk model should capture offset info."""
        chunk = TA6TextChunk(
            chunk_id=0,
            text="Sample chunk text",
            char_start=0,
            char_end=17
        )
        assert chunk.chunk_id == 0
        assert chunk.char_start == 0
        assert chunk.char_end == 17
