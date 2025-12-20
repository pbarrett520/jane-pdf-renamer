"""
Patient information parser module.

Parses patient name and appointment date from PDF text.
HIPAA compliant: No logging of patient information.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
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

# Regex to extract initials from Jane filename
# Pattern: HealthStre_Chart_1_XX_20251218_88209-2.pdf where XX is initials
INITIALS_PATTERN = re.compile(r'_([A-Z]{2})_\d{8}_')


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


def extract_initials_from_filename(filename: str) -> Optional[str]:
    """
    Extract patient initials from Jane PDF filename.
    
    Args:
        filename: The original PDF filename from Jane.
        
    Returns:
        Two-letter initials string, or None if not found.
        
    Example:
        "HealthStre_Chart_1_TP_20251218_88209-2.pdf" -> "TP"
    """
    match = INITIALS_PATTERN.search(filename)
    if match:
        return match.group(1)
    return None


class PatientInfoParser:
    """
    Parses patient name and date from extracted PDF text.
    
    Parsing Rules:
    1. Find line that equals "Chart"
    2. Next non-empty line is patient display name
    3. Strip trailing number from name (e.g., "1" from "Test Patient 1")
    4. Use initials from filename to determine correct first/last split
    5. Find first occurrence of "MonthName DD, YYYY" pattern
    """

    def parse(self, text: str, filename: Optional[str] = None) -> PatientInfo:
        """
        Parse patient information from extracted PDF text.
        
        Args:
            text: Extracted text from PDF.
            filename: Original PDF filename (used to extract initials hint).
            
        Returns:
            PatientInfo with extracted data and confidence score.
        """
        logger.debug("Parsing patient information from text")
        
        # Extract initials from filename if provided
        initials = None
        if filename:
            initials = extract_initials_from_filename(filename)
            logger.debug(f"Extracted initials hint: {initials}")
        
        # Parse components
        first_name, last_name, name_found = self._parse_patient_name(text, initials)
        appointment_date, date_found = self._parse_appointment_date(text)
        
        # Calculate confidence
        confidence = self._calculate_confidence(name_found, date_found, initials is not None)
        
        logger.debug(f"Parse complete: confidence={confidence:.2f}")
        
        return PatientInfo(
            first_name=first_name,
            last_name=last_name,
            appointment_date=appointment_date,
            confidence=confidence
        )

    def _parse_patient_name(self, text: str, initials: Optional[str] = None) -> tuple[str, str, bool]:
        """
        Extract patient name from text.
        
        Args:
            text: Extracted PDF text.
            initials: Two-letter initials from filename (e.g., "TP" for Test Patient).
        
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
        
        # Split into first/last name using initials if available
        parts = name.split()
        
        if len(parts) < 2:
            # Only one word - use as last name
            return '', parts[0] if parts else '', True
        
        # If we have initials, use them to find the correct split point
        if initials and len(initials) == 2:
            first_initial = initials[0].upper()
            last_initial = initials[1].upper()
            
            # Try each possible split point
            for split_idx in range(1, len(parts)):
                potential_first = ' '.join(parts[:split_idx])
                potential_last = ' '.join(parts[split_idx:])
                
                # Check if initials match
                if (potential_first and potential_last and
                    potential_first[0].upper() == first_initial and
                    potential_last[0].upper() == last_initial):
                    return potential_first, potential_last, True
            
            # No match found - fall through to default behavior
            logger.debug("Initials did not match any split point, using default")
        
        # Default: Last word = Last Name, everything before = First Name
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

    def _calculate_confidence(self, name_found: bool, date_found: bool, had_initials: bool) -> float:
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
