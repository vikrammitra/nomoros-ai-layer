"""
TA6-specific text chunking service.

Handles the unique requirements of TA6 Property Information Forms:
- Removes repeated headers/footers (e.g., "Law Society TA6 (5th edition)")
- Chunks with overlap to preserve context across boundaries
- Attempts to avoid splitting mid-question
- Tracks character offsets for evidence citation
"""

import re
from typing import List

from nomoros_ai.models.ta6 import TA6TextChunk


class TA6Chunker:
    """
    Chunker specifically designed for TA6 Property Information Forms.
    
    Strategy:
    1. Normalise text - remove repeated headers/footers
    2. Chunk by ~3,000-3,500 chars with 300 char overlap
    3. Try not to split mid-question (best effort)
    4. Track original character offsets
    """
    
    DEFAULT_CHUNK_SIZE = 3500
    MIN_CHUNK_SIZE = 500
    OVERLAP_SIZE = 300
    
    HEADER_PATTERNS = [
        r"Law Society\s+TA6\s*\([^)]*\)",
        r"Property Information Form\s*\([^)]*\)",
        r"TA6\s*\([^)]*edition[^)]*\)",
        r"^\s*Page\s+\d+\s+of\s+\d+\s*$",
        r"^\s*\d+\s*/\s*\d+\s*$",
        r"Seller['']?s Property Information Form",
        r"Copyright.*Law Society",
    ]
    
    QUESTION_PATTERNS = [
        r"^\s*(\d+\.?\d*)\s*[.:\s]",
        r"^\s*Q\d+",
        r"^\s*Section\s+\d+",
    ]
    
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = OVERLAP_SIZE
    ):
        """
        Initialize the TA6 chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._compiled_headers = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.HEADER_PATTERNS]
        self._compiled_questions = [re.compile(p, re.MULTILINE) for p in self.QUESTION_PATTERNS]
    
    def chunk_text(self, text: str) -> List[TA6TextChunk]:
        """
        Split TA6 text into overlapping chunks.
        
        Args:
            text: Full OCR text from TA6 document
            
        Returns:
            List of TA6TextChunk objects with offset tracking
        """
        if not text or not text.strip():
            return []
        
        original_text = text
        cleaned_text, offset_map = self._normalise_text(text)
        
        if not cleaned_text.strip():
            return []
        
        chunks = []
        current_pos = 0
        chunk_id = 0
        
        while current_pos < len(cleaned_text):
            end_pos = min(current_pos + self.chunk_size, len(cleaned_text))
            
            if end_pos < len(cleaned_text):
                adjusted_end = self._find_break_point(cleaned_text, current_pos, end_pos)
                if adjusted_end > current_pos + self.MIN_CHUNK_SIZE:
                    end_pos = adjusted_end
            
            chunk_text = cleaned_text[current_pos:end_pos]
            
            original_start = self._map_to_original(current_pos, offset_map, len(original_text))
            original_end = self._map_to_original(end_pos, offset_map, len(original_text))
            
            chunks.append(TA6TextChunk(
                chunk_id=chunk_id,
                text=chunk_text.strip(),
                char_start=original_start,
                char_end=original_end
            ))
            
            chunk_id += 1
            next_start = end_pos - self.overlap
            if next_start <= current_pos:
                next_start = end_pos
            current_pos = next_start
            
            if current_pos >= len(cleaned_text):
                break
        
        return chunks
    
    def _normalise_text(self, text: str) -> tuple[str, list[tuple[int, int]]]:
        """
        Remove repeated headers/footers and track offset changes.
        
        Returns:
            Tuple of (cleaned_text, offset_map) where offset_map
            maps cleaned positions to original positions.
        """
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        offset_map = []
        result_chars = []
        original_pos = 0
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_start = original_pos
            is_header = False
            
            for pattern in self._compiled_headers:
                if pattern.search(line):
                    is_header = True
                    break
            
            if is_header:
                original_pos += len(line) + 1
                continue
            
            cleaned_line = self._clean_checkbox_noise(line)
            
            if cleaned_line.strip():
                for char_idx, char in enumerate(cleaned_line):
                    result_chars.append(char)
                    offset_map.append((len(result_chars) - 1, line_start + char_idx))
            
            result_chars.append('\n')
            offset_map.append((len(result_chars) - 1, line_start + len(line)))
            
            original_pos += len(line) + 1
        
        return ''.join(result_chars), offset_map
    
    def _clean_checkbox_noise(self, line: str) -> str:
        """Remove checkbox artifacts like [ ] [X] [✓] from lines."""
        line = re.sub(r'\[\s*[xX✓✗]\s*\]', '', line)
        line = re.sub(r'\[\s*\]', '', line)
        line = re.sub(r'[☐☑☒]', '', line)
        return line
    
    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find the best break point near the target end position.
        
        Prefers:
        1. Before a new question (if within range)
        2. End of paragraph
        3. End of sentence
        4. End of line
        """
        search_start = max(start, end - 500)
        search_text = text[search_start:end]
        
        for pattern in self._compiled_questions:
            for match in pattern.finditer(search_text):
                if match.start() > 100:
                    return search_start + match.start()
        
        para_break = search_text.rfind('\n\n')
        if para_break > 100:
            return search_start + para_break
        
        sentence_end = -1
        for punct in ['. ', '? ', '! ']:
            pos = search_text.rfind(punct)
            if pos > sentence_end:
                sentence_end = pos
        
        if sentence_end > 100:
            return search_start + sentence_end + 2
        
        line_break = search_text.rfind('\n')
        if line_break > 100:
            return search_start + line_break
        
        return end
    
    def _map_to_original(self, cleaned_pos: int, offset_map: list[tuple[int, int]], original_len: int) -> int:
        """Map a position in cleaned text back to original text position."""
        if not offset_map:
            return min(cleaned_pos, original_len)
        
        for cleaned, original in offset_map:
            if cleaned >= cleaned_pos:
                return min(original, original_len)
        
        return original_len
