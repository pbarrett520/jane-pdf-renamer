"""
PDF text extraction module.

Uses pdfplumber for reliable text extraction.
HIPAA compliant: Never writes extracted text to disk or logs.
"""

import logging
from pathlib import Path
from typing import Union

import pdfplumber

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    Extracts text content from PDF files.
    
    HIPAA Compliance:
    - Text is returned in memory only
    - No caching of extracted content
    - No logging of extracted text
    - No writing to disk
    """

    def extract_text(self, pdf_path: Union[str, Path]) -> str:
        """
        Extract all text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            Extracted text as a string with normalized whitespace.
            
        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            Exception: If PDF cannot be read or parsed.
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Log only file path and operation, never content
        logger.debug(f"Extracting text from: {pdf_path}")
        
        try:
            text_parts = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            
            # Join all pages and normalize whitespace
            full_text = "\n".join(text_parts)
            normalized_text = self._normalize_whitespace(full_text)
            
            logger.debug(f"Extraction complete: {len(normalized_text)} characters")
            
            return normalized_text
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {type(e).__name__}")
            raise

    def _normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace in extracted text.
        
        - Preserves line breaks
        - Collapses multiple spaces to single space
        - Strips leading/trailing whitespace from lines
        """
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Collapse multiple spaces and strip
            normalized = ' '.join(line.split())
            normalized_lines.append(normalized)
        
        return '\n'.join(normalized_lines)

