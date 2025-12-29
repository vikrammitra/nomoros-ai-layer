"""
TA6 Property Information Form extraction service.

Uses a map-reduce strategy to handle large TA6 documents (30+ pages):
1. MAP: Extract partial TA6 data from each chunk using Azure OpenAI
2. REDUCE: Merge partial results into one canonical TA6 structure

IMPORTANT:
- LLM is used for EXTRACTION only
- No legal conclusions or risk assessments
- No severity assignments
- All risk decisions are made in the deterministic rules layer
"""

import logging
from typing import List, Dict, Any, Optional

from nomoros_ai.models.ta6 import (
    TA6ExtractionResult,
    TA6ChunkExtraction,
    TA6Section,
    TA6Question,
    TA6Contradiction,
    TA6FollowUp,
    TA6DocumentMeta,
    Evidence,
)
from nomoros_ai.services.chunking.ta6_chunker import TA6Chunker
from nomoros_ai.services.llm.azure_openai_client import AzureOpenAIClient

logger = logging.getLogger(__name__)


class TA6Extractor:
    """
    Extracts structured data from TA6 Property Information Forms.
    
    Workflow:
    1. Chunk OCR text with TA6-specific chunker (header removal, overlap)
    2. MAP: For each chunk, call Azure OpenAI with strict extraction prompt
    3. REDUCE: Merge sections/questions, deduplicate evidence, merge contradictions
    4. Generate final follow-up questions list
    5. Return structured TA6ExtractionResult
    """
    
    SYSTEM_PROMPT = """You are a legal document extraction engine.
Extract factual seller disclosures only from a UK TA6 Property Information Form.
Do not infer. Do not assess risk. Do not provide legal advice.
Return JSON only."""

    USER_PROMPT_TEMPLATE = """You are given PARTIAL text from a TA6 form.

TASK:
- Confirm if this text belongs to a TA6 Property Information Form
- Extract any TA6 questions + answers present in this chunk
- Capture checkboxes as yes/no where explicit tick marks are indicated
- Record missing or unclear answers
- Capture evidence quotes with character offsets (relative to chunk start: 0 to {chunk_len})
- Do NOT assume missing sections exist - only extract what is present

CRITICAL RULES:
- Never hallucinate missing answers
- Absence of a tick ≠ "No" - mark as "missing"
- "See attached" without attachment content → add to missing_or_referenced_attachments
- Evidence quotes max 25 words
- If no TA6 content is present in this chunk, return: {{ "is_ta6": false }}

Return valid JSON matching this structure:
{{
  "is_ta6": true,
  "document_meta": {{
    "property_address": "Address if found, null otherwise",
    "seller_names": ["Name if found"],
    "form_date": "Date if found, null otherwise",
    "form_version": "Edition if found, null otherwise"
  }},
  "sections": [
    {{
      "section_name": "Section title",
      "questions": [
        {{
          "question_id": "1.1",
          "question_text": "Question text",
          "answer_normalised": "yes|no|unknown|not_applicable|details_provided",
          "answer_raw": "Raw answer text",
          "details": "Additional details if any",
          "answer_status": "clear|unclear|missing|contradictory",
          "clarification_question": "Follow-up question if unclear",
          "evidence": [
            {{
              "ref": "1.1",
              "quote": "Direct quote max 25 words",
              "char_start": 0,
              "char_end": 100
            }}
          ]
        }}
      ]
    }}
  ],
  "contradictions": [],
  "missing_or_referenced_attachments": [],
  "follow_up_questions": []
}}

Text (chunk {chunk_id}, chars 0-{chunk_len}):
{chunk_text}"""

    def __init__(self, openai_client: AzureOpenAIClient | None = None):
        """
        Initialize extractor with optional OpenAI client.
        
        Args:
            openai_client: Azure OpenAI client instance. If None, creates new one.
        """
        self.chunker = TA6Chunker()
        self.openai_client = openai_client or AzureOpenAIClient()
    
    def extract(self, ocr_text: str) -> TA6ExtractionResult:
        """
        Extract TA6 data from OCR text using map-reduce strategy.
        
        Args:
            ocr_text: Full OCR text from the document
            
        Returns:
            TA6ExtractionResult with aggregated findings
        """
        if not ocr_text or not ocr_text.strip():
            logger.warning("Empty OCR text provided")
            return TA6ExtractionResult(is_ta6=False)
        
        if not self.openai_client.is_configured:
            logger.warning("Azure OpenAI not configured - cannot extract TA6")
            return TA6ExtractionResult(is_ta6=False)
        
        chunks = self.chunker.chunk_text(ocr_text)
        logger.info(f"Split TA6 document into {len(chunks)} chunks")
        
        if not chunks:
            return TA6ExtractionResult(is_ta6=False)
        
        chunk_extractions: List[TA6ChunkExtraction] = []
        failed_chunks = 0
        
        for chunk in chunks:
            try:
                result = self._extract_from_chunk(chunk.chunk_id, chunk.text)
                chunk_extractions.append(result)
            except Exception as e:
                logger.error(f"Error extracting from chunk {chunk.chunk_id}: {e}")
                failed_chunks += 1
                continue
        
        if failed_chunks == len(chunks):
            logger.warning("All Azure OpenAI extractions failed for TA6")
            return TA6ExtractionResult(is_ta6=False)
        
        ta6_chunks = [ext for ext in chunk_extractions if ext.is_ta6]
        if not ta6_chunks:
            logger.info("No TA6 content detected in any chunk")
            return TA6ExtractionResult(is_ta6=False)
        
        return self._reduce_extractions(ta6_chunks, len(chunks))
    
    def _extract_from_chunk(self, chunk_id: int, chunk_text: str) -> TA6ChunkExtraction:
        """
        MAP phase: Extract data from a single text chunk using Azure OpenAI.
        """
        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            chunk_id=chunk_id,
            chunk_len=len(chunk_text),
            chunk_text=chunk_text
        )
        
        result = self.openai_client.extract_structured(
            text_chunk=chunk_text,
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt
        )
        
        if not result.get("is_ta6", False):
            return TA6ChunkExtraction(is_ta6=False, document_meta=None)
        
        sections = self._parse_sections(result.get("sections", []))
        contradictions = self._parse_contradictions(result.get("contradictions", []))
        follow_ups = self._parse_follow_ups(result.get("follow_up_questions", []))
        meta = self._parse_document_meta(result.get("document_meta", {}))
        
        return TA6ChunkExtraction(
            is_ta6=True,
            sections=sections,
            contradictions=contradictions,
            missing_or_referenced_attachments=result.get("missing_or_referenced_attachments", []),
            follow_up_questions=follow_ups,
            document_meta=meta
        )
    
    def _reduce_extractions(
        self,
        extractions: List[TA6ChunkExtraction],
        total_chunks: int
    ) -> TA6ExtractionResult:
        """
        REDUCE phase: Merge partial results into canonical TA6 structure.
        """
        merged_sections: Dict[str, Dict[str, TA6Question]] = {}
        merged_contradictions: List[TA6Contradiction] = []
        merged_attachments: List[dict] = []
        merged_follow_ups: Dict[str, TA6FollowUp] = {}
        merged_meta = TA6DocumentMeta()
        
        for ext in extractions:
            if ext.document_meta:
                if ext.document_meta.property_address and not merged_meta.property_address:
                    merged_meta.property_address = ext.document_meta.property_address
                if ext.document_meta.form_date and not merged_meta.form_date:
                    merged_meta.form_date = ext.document_meta.form_date
                if ext.document_meta.form_version and not merged_meta.form_version:
                    merged_meta.form_version = ext.document_meta.form_version
                for name in ext.document_meta.seller_names:
                    if name not in merged_meta.seller_names:
                        merged_meta.seller_names.append(name)
            
            for section in ext.sections:
                if section.section_name not in merged_sections:
                    merged_sections[section.section_name] = {}
                
                for question in section.questions:
                    q_key = question.question_id or question.question_text[:50]
                    
                    if q_key not in merged_sections[section.section_name]:
                        merged_sections[section.section_name][q_key] = question
                    else:
                        existing = merged_sections[section.section_name][q_key]
                        merged_sections[section.section_name][q_key] = self._merge_questions(existing, question)
            
            merged_contradictions.extend(ext.contradictions)
            merged_attachments.extend(ext.missing_or_referenced_attachments)
            
            for fu in ext.follow_up_questions:
                fu_key = fu.question[:50]
                if fu_key not in merged_follow_ups:
                    merged_follow_ups[fu_key] = fu
                elif fu.priority == "high" and merged_follow_ups[fu_key].priority != "high":
                    merged_follow_ups[fu_key] = fu
        
        final_sections = []
        for section_name, questions in merged_sections.items():
            sorted_questions = sorted(questions.values(), key=lambda q: q.question_id or q.question_text)
            final_sections.append(TA6Section(
                section_name=section_name,
                questions=sorted_questions
            ))
        
        final_sections.sort(key=lambda s: s.section_name)
        
        unique_contradictions = self._deduplicate_contradictions(merged_contradictions)
        unique_attachments = self._deduplicate_attachments(merged_attachments)
        final_follow_ups = sorted(
            merged_follow_ups.values(),
            key=lambda f: (0 if f.priority == "high" else 1 if f.priority == "medium" else 2, f.question)
        )
        
        return TA6ExtractionResult(
            is_ta6=True,
            document_meta=merged_meta,
            sections=final_sections,
            contradictions=unique_contradictions,
            missing_or_referenced_attachments=unique_attachments,
            follow_up_questions=final_follow_ups
        )
    
    def _merge_questions(self, existing: TA6Question, new: TA6Question) -> TA6Question:
        """Merge two questions, keeping the most complete information."""
        merged_evidence = list(existing.evidence)
        existing_quotes = {e.quote for e in existing.evidence}
        for e in new.evidence:
            if e.quote not in existing_quotes:
                merged_evidence.append(e)
        
        answer_normalised = existing.answer_normalised
        answer_status = existing.answer_status
        
        if existing.answer_normalised != new.answer_normalised:
            if existing.answer_normalised == "unknown" or existing.answer_status == "missing":
                answer_normalised = new.answer_normalised
                answer_status = new.answer_status
            elif new.answer_normalised != "unknown" and new.answer_status != "missing":
                if existing.answer_normalised != new.answer_normalised:
                    answer_status = "contradictory"
        
        details = existing.details
        if new.details and not existing.details:
            details = new.details
        elif new.details and existing.details and new.details not in existing.details:
            details = f"{existing.details}; {new.details}"
        
        return TA6Question(
            question_id=existing.question_id or new.question_id,
            question_text=existing.question_text,
            answer_normalised=answer_normalised,
            answer_raw=existing.answer_raw or new.answer_raw,
            details=details,
            answer_status=answer_status,
            clarification_question=existing.clarification_question or new.clarification_question,
            evidence=merged_evidence
        )
    
    def _parse_sections(self, sections_data: List[dict]) -> List[TA6Section]:
        """Parse sections from LLM output."""
        sections = []
        for s in sections_data:
            questions = []
            for q in s.get("questions", []):
                evidence = []
                for e in q.get("evidence", []):
                    try:
                        evidence.append(Evidence(
                            ref=e.get("ref"),
                            quote=e.get("quote", "")[:100],
                            char_start=int(e.get("char_start", 0)),
                            char_end=int(e.get("char_end", 0))
                        ))
                    except (ValueError, TypeError):
                        continue
                
                try:
                    questions.append(TA6Question(
                        question_id=q.get("question_id"),
                        question_text=q.get("question_text", "Unknown question"),
                        answer_normalised=q.get("answer_normalised", "unknown"),
                        answer_raw=q.get("answer_raw"),
                        details=q.get("details"),
                        answer_status=q.get("answer_status", "clear"),
                        clarification_question=q.get("clarification_question"),
                        evidence=evidence
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse question: {e}")
                    continue
            
            if questions:
                sections.append(TA6Section(
                    section_name=s.get("section_name", "Unknown Section"),
                    questions=questions
                ))
        return sections
    
    def _parse_contradictions(self, contradictions_data: List[dict]) -> List[TA6Contradiction]:
        """Parse contradictions from LLM output."""
        contradictions = []
        for c in contradictions_data:
            try:
                contradictions.append(TA6Contradiction(
                    type=c.get("type", "unknown"),
                    description=c.get("description", ""),
                    items=c.get("items", [])
                ))
            except Exception:
                continue
        return contradictions
    
    def _parse_follow_ups(self, follow_ups_data: List[dict]) -> List[TA6FollowUp]:
        """Parse follow-up questions from LLM output."""
        follow_ups = []
        for f in follow_ups_data:
            try:
                priority = f.get("priority", "medium")
                if priority not in ["high", "medium", "low"]:
                    priority = "medium"
                reason = f.get("reason", "unclear")
                if reason not in ["missing", "unclear", "contradiction", "attachment_referenced"]:
                    reason = "unclear"
                follow_ups.append(TA6FollowUp(
                    priority=priority,
                    question=f.get("question", ""),
                    reason=reason
                ))
            except Exception:
                continue
        return follow_ups
    
    def _parse_document_meta(self, meta_data: dict) -> Optional[TA6DocumentMeta]:
        """Parse document metadata from LLM output."""
        if not meta_data:
            return None
        try:
            return TA6DocumentMeta(
                property_address=meta_data.get("property_address"),
                seller_names=meta_data.get("seller_names", []),
                form_date=meta_data.get("form_date"),
                form_version=meta_data.get("form_version")
            )
        except Exception:
            return None
    
    def _deduplicate_contradictions(self, contradictions: List[TA6Contradiction]) -> List[TA6Contradiction]:
        """Remove duplicate contradictions."""
        seen = set()
        unique = []
        for c in contradictions:
            key = (c.type, c.description)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique
    
    def _deduplicate_attachments(self, attachments: List[dict]) -> List[dict]:
        """Remove duplicate attachments."""
        seen = set()
        unique = []
        for a in attachments:
            key = str(sorted(a.items()) if isinstance(a, dict) else a)
            if key not in seen:
                seen.add(key)
                unique.append(a)
        return unique
