import logging
from typing import List, Optional
from app.ingestion.extraction import ExtractedPage

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a split chunk of text prepared for embedding generation."""
    def __init__(self, index: int, content: str, page_number: int, section_title: Optional[str] = None) -> None:
        self.index = index
        self.content = content
        self.page_number = page_number
        self.section_title = section_title


class RecursiveCharacterTextSplitter:
    """Split text recursively using a list of separators to keep paragraphs and sentences together."""

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 250,
        chunk_cross_page: bool = False,
        chunk_splitter_type: str = "recursive"
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_cross_page = chunk_cross_page
        self.chunk_splitter_type = chunk_splitter_type
        self.separators = ["\n\n", "\n", " ", ""]

    def _split_character_only(self, text: str) -> List[str]:
        """Split text strictly by character count with overlap, ignoring paragraph/newline hierarchy."""
        chunks = []
        start = 0
        if self.chunk_size <= 0:
            return [text]
        step = self.chunk_size - self.chunk_overlap
        if step <= 0:
            step = 1
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += step
        return chunks

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Split text recursively."""
        final_chunks = []
        
        # Get first separator
        separator = separators[0]
        next_separators = separators[1:]
        
        # Split by separator
        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)
            
        # Recombine splits
        current_chunk = []
        current_len = 0
        
        for split in splits:
            # If the single split is larger than chunk_size, split it recursively with remaining separators
            if len(split) > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    final_chunks.append(separator.join(current_chunk))
                    current_chunk = []
                    current_len = 0
                    
                if next_separators:
                    recursed = self._split_text(split, next_separators)
                    final_chunks.extend(recursed)
                else:
                    # No separators left, force-split by characters
                    start = 0
                    while start < len(split):
                        final_chunks.append(split[start:start + self.chunk_size])
                        start += self.chunk_size - self.chunk_overlap
            else:
                # If adding this split exceeds chunk_size, flush and start a new chunk
                # Note: include separators in length calculation
                split_len = len(split) + (len(separator) if current_chunk else 0)
                if current_len + split_len > self.chunk_size:
                    final_chunks.append(separator.join(current_chunk))
                    
                    # Backtrack for overlap
                    overlap_splits = []
                    overlap_len = 0
                    for prev_split in reversed(current_chunk):
                        prev_len = len(prev_split) + (len(separator) if overlap_splits else 0)
                        if overlap_len + prev_len <= self.chunk_overlap:
                            overlap_splits.insert(0, prev_split)
                            overlap_len += prev_len
                        else:
                            break
                            
                    current_chunk = overlap_splits
                    current_len = overlap_len
                    
                current_chunk.append(split)
                current_len += len(split) + (len(separator) if len(current_chunk) > 1 else 0)
                
        if current_chunk:
            final_chunks.append(separator.join(current_chunk))
            
        return final_chunks

    def split_pages(self, pages: List[ExtractedPage]) -> List[DocumentChunk]:
        """Process page-by-page text blocks and return recursive overlapping chunks with section titles.

        Maintains accurate page numbering references and extracts section titles.
        """
        import re
        # Czech-friendly decimal numbering section header regex
        SECTION_REGEX = re.compile(r'^\s*(\d+(?:\.\d+)*\.?\s+[^\W\d_].*?)\s*$', re.MULTILINE)

        chunks = []
        chunk_counter = 0

        if self.chunk_cross_page:
            # CROSS-PAGE CHUNKING STRATEGY
            # 1. Concatenate all page texts and keep track of character offsets per page boundary
            concat_text = ""
            page_boundaries = []  # List of tuples: (start_idx, end_idx, page_number, headers)
            for page in pages:
                start = len(concat_text)
                concat_text += page.text + "\n"
                end = len(concat_text)
                
                # Extract headers for this page and translate start offset to global concat offset
                headers = []
                for match in SECTION_REGEX.finditer(page.text):
                    global_header_start = start + match.start()
                    headers.append((global_header_start, match.group(1).strip()))
                
                page_boundaries.append((start, end, page.page_number, headers))

            # 2. Split the concatenated continuous text string
            if self.chunk_splitter_type == "character":
                splits = self._split_character_only(concat_text)
            else:
                splits = self._split_text(concat_text, self.separators)

            # 3. Resolve page number, section title, and offsets sequentially
            current_offset = 0
            active_section = None
            
            for content in splits:
                content_stripped = content.strip()
                if not content_stripped:
                    continue

                # Find start offset in concatenated text to determine page and section mapping
                start_idx = concat_text.find(content_stripped, current_offset)
                if start_idx == -1:
                    start_idx = current_offset
                else:
                    current_offset = start_idx + len(content_stripped)

                # Determine which page this chunk starts on
                chunk_page = 1
                chunk_headers = []
                for p_start, p_end, p_num, p_headers in page_boundaries:
                    if p_start <= start_idx < p_end:
                        chunk_page = p_num
                    # Collect all headers for section resolution
                    chunk_headers.extend(p_headers)

                # Sort headers by global start offset to find active section
                chunk_headers.sort(key=lambda x: x[0])
                
                chunk_section = active_section
                for h_start, h_title in chunk_headers:
                    if h_start <= start_idx:
                        chunk_section = h_title
                    else:
                        break

                if chunk_section != active_section:
                    active_section = chunk_section

                chunks.append(
                    DocumentChunk(
                        index=chunk_counter,
                        content=content_stripped,
                        page_number=chunk_page,
                        section_title=chunk_section,
                    )
                )
                chunk_counter += 1
        else:
            # PAGE-ISOLATED CHUNKING STRATEGY (default)
            active_section = None
            for page in pages:
                text = page.text
                if not text.strip():
                    continue

                # Find all section headers on the current page
                headers = []
                for match in SECTION_REGEX.finditer(text):
                    headers.append((match.start(), match.group(1).strip()))

                # Split text on this page
                if self.chunk_splitter_type == "character":
                    page_splits = self._split_character_only(text)
                else:
                    page_splits = self._split_text(text, self.separators)

                # Reconstruct character start offsets to resolve sections
                current_offset = 0
                for content in page_splits:
                    content_stripped = content.strip()
                    if not content_stripped:
                        continue

                    start_idx = text.find(content_stripped, current_offset)
                    if start_idx == -1:
                        start_idx = current_offset
                    else:
                        current_offset = start_idx + len(content_stripped)

                    # Resolve active section title
                    chunk_section = active_section
                    for h_start, h_title in headers:
                        if h_start <= start_idx:
                            chunk_section = h_title
                        else:
                            break

                    if chunk_section != active_section:
                        active_section = chunk_section

                    chunks.append(
                        DocumentChunk(
                            index=chunk_counter,
                            content=content_stripped,
                            page_number=page.page_number,
                            section_title=chunk_section,
                        )
                    )
                    chunk_counter += 1

        logger.info(f"Split {len(pages)} pages using strategy (cross_page={self.chunk_cross_page}, type={self.chunk_splitter_type}) into {len(chunks)} chunks.")
        return chunks
