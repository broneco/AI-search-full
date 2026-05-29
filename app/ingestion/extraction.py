import os
import logging
from typing import Dict, List
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class ExtractedPage:
    """Represents text content parsed from a single document page."""
    def __init__(self, page_number: int, text: str) -> None:
        self.page_number = page_number
        self.text = text


class DocumentExtractor:
    """Extract text from local files (PDFs and standard text files)."""

    def extract(self, file_path: str) -> List[ExtractedPage]:
        """Determine file type and extract page-by-page text blocks.

        Supports .pdf and .txt files.
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext == ".pdf":
            return self._extract_pdf(file_path)
        elif ext == ".txt":
            return self._extract_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format for extraction: {ext}")

    def _extract_pdf(self, file_path: str) -> List[ExtractedPage]:
        logger.info(f"Extracting text from PDF: {file_path}")
        pages = []
        
        try:
            reader = PdfReader(file_path)
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                # Strip excessive spaces but preserve basic paragraphs
                clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                pages.append(ExtractedPage(page_number=idx + 1, text=clean_text))
            
            logger.info(f"Successfully extracted {len(pages)} pages from PDF: {file_path}")
            return pages
        except Exception as e:
            logger.error(f"Failed to extract PDF text from {file_path}: {e}")
            raise

    def _extract_txt(self, file_path: str) -> List[ExtractedPage]:
        logger.info(f"Extracting text from TXT: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Text file represents a single page
            return [ExtractedPage(page_number=1, text=content)]
        except Exception as e:
            logger.error(f"Failed to read text file {file_path}: {e}")
            raise
