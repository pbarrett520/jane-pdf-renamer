"""
Patient information parser module.

Parses patient name and appointment date from PDF text.
HIPAA compliant: No logging of patient information.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


# Month name to number mapping
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}

# Regex for date pattern: MonthName DD, YYYY
DATE_PATTERN = re.compile(
    r'\b(January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+(\d{1,2}),\s*(\d{4})\b',
    re.IGNORECASE
)

# Regex to detect trailing number in patient name (e.g., "Test Patient 1")
TRAILING_NUMBER_PATTERN = re.compile(r'\s+\d+$')


@dataclass
class PatientInfo:
    """Parsed patient information from PDF."""
    first_name: str
    last_name: str
    appointment_date: Optional[date]
    confidence: float  # 0.0 to 1.0

    def is_complete(self) -> bool:
        """Check if all required fields are present."""
        return bool(
            self.first_name and 
            self.last_name and 
            self.appointment_date
        )

    def needs_review(self) -> bool:
        """Check if manual review is needed."""
        return self.confidence < 0.9 or not self.is_complete()


class PatientInfoParser:
    """
    Parses patient name and date from extracted PDF text.
    
    Parsing Rules:
    1. Find line that equals "Chart"
    2. Next non-empty line is patient display name
    3. Strip trailing number from name (e.g., "1" from "Test Patient 1")
    4. Split by spaces: last word = Last Name, rest = First Name
    5. Find first occurrence of "MonthName DD, YYYY" pattern
    """

    def parse(self, text: str) -> PatientInfo:
        """
        Parse patient information from extracted PDF text.
        
        Args:
            text: Extracted text from PDF.
            
        Returns:
            PatientInfo with extracted data and confidence score.
        """
        logger.debug("Parsing patient information from text")
        
        # Parse components
        first_name, last_name, name_found = self._parse_patient_name(text)
        appointment_date, date_found = self._parse_appointment_date(text)
        
        # Calculate confidence
        confidence = self._calculate_confidence(name_found, date_found)
        
        logger.debug(f"Parse complete: confidence={confidence:.2f}")
        
        return PatientInfo(
            first_name=first_name,
            last_name=last_name,
            appointment_date=appointment_date,
            confidence=confidence
        )

    def _parse_patient_name(self, text: str) -> tuple[str, str, bool]:
        """
        Extract patient name from text.
        
        Returns:
            Tuple of (first_name, last_name, found_flag)
        """
        lines = text.split('\n')
        
        # Find "Chart" line
        chart_index = None
        for i, line in enumerate(lines):
            if line.strip().lower() == 'chart':
                chart_index = i
                break
        
        if chart_index is None:
            return '', '', False
        
        # Find next non-empty line after "Chart"
        patient_name_line = None
        for line in lines[chart_index + 1:]:
            stripped = line.strip()
            if stripped:
                patient_name_line = stripped
                break
        
        if not patient_name_line:
            return '', '', False
        
        # Strip trailing number (e.g., "Test Patient 1" -> "Test Patient")
        name = TRAILING_NUMBER_PATTERN.sub('', patient_name_line).strip()
        
        # Split into first/last name
        # Last word = Last Name, everything before = First Name
        parts = name.split()
        
        if len(parts) < 2:
            # Only one word - use as last name
            return '', parts[0] if parts else '', True
        
        last_name = parts[-1]
        first_name = ' '.join(parts[:-1])
        
        return first_name, last_name, True

    def _parse_appointment_date(self, text: str) -> tuple[Optional[date], bool]:
        """
        Extract appointment date from text.
        
        Returns:
            Tuple of (date_object, found_flag)
        """
        match = DATE_PATTERN.search(text)
        
        if not match:
            return None, False
        
        month_name = match.group(1).lower()
        day = int(match.group(2))
        year = int(match.group(3))
        
        month = MONTH_MAP.get(month_name)
        
        if not month:
            return None, False
        
        try:
            return date(year, month, day), True
        except ValueError:
            # Invalid date
            return None, False

    def _calculate_confidence(self, name_found: bool, date_found: bool) -> float:
        """
        Calculate confidence score based on what was found.
        
        Returns:
            Float between 0.0 and 1.0
        """
        if name_found and date_found:
            return 1.0
        elif name_found or date_found:
            return 0.5
        else:
            return 0.0

