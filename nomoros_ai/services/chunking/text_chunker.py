"""
Text chunking service for LLM-safe document analysis.

Splits OCR text into manageable chunks while preserving context.
Used for feeding text to Azure OpenAI for extraction tasks.
"""

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    """A chunk of text with metadata."""
    content: str
    chunk_index: int
    section_title: str | None = None


class TextChunker:
    """
    Chunks OCR text for LLM processing.
    
    Strategy:
    1. Try to split by section headings first (preserves logical boundaries)
    2. Fall back to fixed-size chunks if no headings detected
    3. Ensure each chunk is within token-safe limits
    """
    
    # Target chunk size in characters (approx 300-400 tokens)
    DEFAULT_CHUNK_SIZE = 1200
    MAX_CHUNK_SIZE = 1500
    MIN_CHUNK_SIZE = 200
    
    # Common section heading patterns in Local Authority Searches
    SECTION_PATTERNS = [
        r"^(?:SECTION\s+)?(\d+(?:\.\d+)?)[.\s]+([A-Z][A-Za-z\s]+)",  # "1. Planning" or "SECTION 1 Planning"
        r"^(CON29[RO]?\s*Q?\d+)[.\s:]+",  # "CON29R Q1:" format
        r"^(Part\s+[IVX\d]+)[.\s:]+",  # "Part I:" format
        r"^([A-Z][A-Z\s]{5,}):?\s*$",  # ALL CAPS HEADINGS
    ]
    
    def chunk_text(self, text: str) -> list[TextChunk]:
        """
        Split text into LLM-safe chunks.
        
        Args:
            text: Full OCR text from document
            
        Returns:
            List of TextChunk objects with content and metadata
        """
        if not text or not text.strip():
            return []
        
        # Normalize whitespace
        text = self._normalize_text(text)
        
        # Try section-based chunking first
        sections = self._split_by_sections(text)
        
        if sections:
            # Process sections into chunks
            chunks = self._sections_to_chunks(sections)
        else:
            # Fall back to fixed-size chunking
            chunks = self._fixed_size_chunks(text)
        
        return chunks
    
    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and line endings."""
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Collapse multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _split_by_sections(self, text: str) -> list[tuple[str, str]]:
        """
        Try to split text by section headings.
        
        Returns:
            List of (section_title, section_content) tuples
        """
        lines = text.split('\n')
        sections = []
        current_section = None
        current_content = []
        
        for line in lines:
            is_heading = False
            heading_match = None
            
            # Check if line matches any heading pattern
            for pattern in self.SECTION_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    is_heading = True
                    heading_match = line.strip()
                    break
            
            if is_heading:
                # Save previous section
                if current_section or current_content:
                    sections.append((
                        current_section or "Introduction",
                        '\n'.join(current_content)
                    ))
                current_section = heading_match
                current_content = []
            else:
                current_content.append(line)
        
        # Don't forget the last section
        if current_section or current_content:
            sections.append((
                current_section or "Document Content",
                '\n'.join(current_content)
            ))
        
        # Only return sections if we found meaningful structure
        if len(sections) > 1:
            return sections
        return []
    
    def _sections_to_chunks(self, sections: list[tuple[str, str]]) -> list[TextChunk]:
        """
        Convert sections to chunks, splitting large sections if needed.
        """
        chunks = []
        chunk_index = 0
        
        for section_title, content in sections:
            content = content.strip()
            if not content:
                continue
            
            # If section is within size limit, keep it whole
            if len(content) <= self.MAX_CHUNK_SIZE:
                chunks.append(TextChunk(
                    content=f"[{section_title}]\n{content}",
                    chunk_index=chunk_index,
                    section_title=section_title
                ))
                chunk_index += 1
            else:
                # Split large section into sub-chunks
                sub_chunks = self._split_large_text(content, section_title)
                for sub in sub_chunks:
                    chunks.append(TextChunk(
                        content=f"[{section_title}]\n{sub}",
                        chunk_index=chunk_index,
                        section_title=section_title
                    ))
                    chunk_index += 1
        
        return chunks
    
    def _fixed_size_chunks(self, text: str) -> list[TextChunk]:
        """
        Split text into fixed-size chunks when no sections detected.
        Tries to break at paragraph or sentence boundaries.
        """
        chunks = []
        paragraphs = text.split('\n\n')
        
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_size = len(para)
            
            # If single paragraph exceeds max, split it
            if para_size > self.MAX_CHUNK_SIZE:
                # Save current chunk first
                if current_chunk:
                    chunks.append(TextChunk(
                        content='\n\n'.join(current_chunk),
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_size = 0
                
                # Split the large paragraph
                sub_chunks = self._split_large_text(para)
                for sub in sub_chunks:
                    chunks.append(TextChunk(
                        content=sub,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1
            
            # If adding paragraph exceeds target, start new chunk
            elif current_size + para_size > self.DEFAULT_CHUNK_SIZE:
                if current_chunk:
                    chunks.append(TextChunk(
                        content='\n\n'.join(current_chunk),
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1
                current_chunk = [para]
                current_size = para_size
            
            else:
                current_chunk.append(para)
                current_size += para_size
        
        # Don't forget the last chunk
        if current_chunk:
            chunks.append(TextChunk(
                content='\n\n'.join(current_chunk),
                chunk_index=chunk_index
            ))
        
        return chunks
    
    def _split_large_text(self, text: str, section_title: str | None = None) -> list[str]:
        """
        Split a large block of text at sentence boundaries.
        """
        # Split by sentences (simple approach)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        sub_chunks = []
        current = []
        current_size = 0
        
        for sentence in sentences:
            sent_size = len(sentence)
            
            if current_size + sent_size > self.DEFAULT_CHUNK_SIZE and current:
                sub_chunks.append(' '.join(current))
                current = [sentence]
                current_size = sent_size
            else:
                current.append(sentence)
                current_size += sent_size
        
        if current:
            sub_chunks.append(' '.join(current))
        
        return sub_chunks
