import logging
from typing import List
from app.ingestion.extraction import ExtractedPage

logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a split chunk of text prepared for embedding generation."""
    def __init__(self, index: int, content: str, page_number: int) -> None:
        self.index = index
        self.content = content
        self.page_number = page_number


class CharacterTextSplitter:
    """Split extracted page text into clean segments using character count limits and overlaps."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150) -> None:
        """Initialize parameters."""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_pages(self, pages: List[ExtractedPage]) -> List[DocumentChunk]:
        """Process page-by-page text blocks and return a list of overlapping chunks.

        Maintains accurate page numbering references.
        """
        chunks = []
        chunk_counter = 0

        for page in pages:
            text = page.text
            if not text.strip():
                continue

            start = 0
            text_len = len(text)

            while start < text_len:
                end = min(start + self.chunk_size, text_len)
                
                # Try to adjust chunk boundary to end gracefully on a newline or space
                if end < text_len:
                    # Search backward up to 100 characters for a natural boundary
                    boundary = text.rfind("\n", end - 100, end)
                    if boundary == -1:
                        boundary = text.rfind(" ", end - 50, end)
                    
                    if boundary != -1:
                        end = boundary + 1

                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append(
                        DocumentChunk(
                            index=chunk_counter,
                            content=chunk_text,
                            page_number=page.page_number,
                        )
                    )
                    chunk_counter += 1

                # If we have reached the end of the page text, exit the split loop
                if end == text_len:
                    break

                # Advance start window taking overlap into account
                next_start = end - self.chunk_overlap
                if next_start <= start:
                    # Force forward progress to prevent infinite loop
                    start = end
                else:
                    start = next_start

        logger.info(f"Split {len(pages)} pages into {len(chunks)} contextual chunks.")
        return chunks
