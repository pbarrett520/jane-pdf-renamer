"""
File renaming module.

Handles renaming PDFs with proper naming convention and collision handling.
HIPAA compliant: Logs only file paths and hashes, never patient info.
"""

import hashlib
import logging
import shutil
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from .parser import PatientInfo

logger = logging.getLogger(__name__)


class FileFormat(str, Enum):
    """Available filename formats."""
    CURRENT_DISCHARGE = "current_discharge"
    APPT_BILLING = "appt_billing"
    APPT_BILLING_EVAL = "appt_billing_eval"
    APPT_BILLING_PROGRESS = "appt_billing_progress"
    APPT_BILLING_DISCHARGE = "appt_billing_discharge"


# Format configurations: (use_current_date, suffix)
FORMAT_CONFIG = {
    FileFormat.CURRENT_DISCHARGE: (True, "PT Chart Note"),
    FileFormat.APPT_BILLING: (False, "PT Note"),
    FileFormat.APPT_BILLING_EVAL: (False, "PT Eval Note"),
    FileFormat.APPT_BILLING_PROGRESS: (False, "PT Progress Note"),
    FileFormat.APPT_BILLING_DISCHARGE: (False, "PT Discharge Note"),
}


class FileRenamer:
    """
    Renames PDF files according to the naming convention.
    
    Naming Convention:
        Last, First MMDDYY <Suffix>.pdf
        
    Collision Handling:
        If target filename exists, append _<shorthash> before .pdf
    """

    def __init__(
        self, 
        output_folder: Optional[Union[str, Path]] = None,
        file_format: FileFormat = FileFormat.APPT_BILLING
    ):
        """
        Initialize renamer.
        
        Args:
            output_folder: Optional folder to move renamed files to.
                          If None, files are renamed in place.
            file_format: The filename format to use.
        """
        self.output_folder = Path(output_folder) if output_folder else None
        self.file_format = file_format

    def generate_filename(
        self, 
        info: PatientInfo,
        file_format: Optional[FileFormat] = None
    ) -> str:
        """
        Generate the target filename from patient info.
        
        Args:
            info: Parsed patient information.
            file_format: Override format (uses instance format if None).
            
        Returns:
            Formatted filename string.
        """
        fmt = file_format or self.file_format
        use_current_date, suffix = FORMAT_CONFIG[fmt]
        
        # Determine the date string to use
        # When DOI/DOB is present, include BOTH the code AND the appropriate date
        if info.date_code:
            # Include DOI/DOB code plus the appropriate date
            if use_current_date:
                date_part = date.today().strftime("%m%d%y")
            elif info.appointment_date:
                date_part = info.appointment_date.strftime("%m%d%y")
            else:
                # Fallback to just the date code if no other date available
                date_part = None
            
            if date_part:
                date_str = f"{info.date_code} {date_part}"
            else:
                date_str = info.date_code
        elif use_current_date:
            target_date = date.today()
            date_str = target_date.strftime("%m%d%y")
        elif info.appointment_date:
            target_date = info.appointment_date
            date_str = target_date.strftime("%m%d%y")
        else:
            raise ValueError("Cannot generate filename without appointment date or date code")
        
        # Build filename: Last, First DATESTR Suffix.pdf
        # DATESTR is either MMDDYY or DOI/DOB code like "DOI010125"
        filename = f"{info.last_name}, {info.first_name} {date_str} {suffix}.pdf"
        
        # Sanitize filename to remove characters that are invalid in file paths
        # Replace forward/back slashes and other problematic characters
        filename = self._sanitize_filename(filename)
        
        return filename
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Remove or replace characters that are invalid in filenames.
        
        Args:
            filename: The proposed filename.
            
        Returns:
            Sanitized filename safe for filesystem use.
        """
        # Characters that are problematic in filenames across platforms
        # / and \ are path separators, : is problematic on Windows/macOS
        # < > " | ? * are invalid on Windows
        invalid_chars = ['/', '\\', ':', '<', '>', '"', '|', '?', '*']
        
        result = filename
        for char in invalid_chars:
            result = result.replace(char, '')
        
        return result

    def rename_file(
        self, 
        source_path: Union[str, Path], 
        info: PatientInfo,
        file_format: Optional[FileFormat] = None
    ) -> Path:
        """
        Rename a PDF file according to the naming convention.
        
        Args:
            source_path: Path to the source PDF file.
            info: Parsed patient information.
            file_format: Override format (uses instance format if None).
            
        Returns:
            Path to the renamed file.
            
        Raises:
            FileNotFoundError: If source file doesn't exist.
            ValueError: If patient info is incomplete.
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Generate target filename
        filename = self.generate_filename(info, file_format)
        
        # Determine target directory
        if self.output_folder:
            target_dir = self.output_folder
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = source_path.parent
        
        target_path = target_dir / filename
        
        # Handle collision - but check if the existing file is identical first
        if target_path.exists() and target_path != source_path:
            # Check if files are identical (same content)
            if self._files_are_identical(source_path, target_path):
                logger.info(f"Target file identical to source, replacing: {target_path.name}")
                # Remove the existing file since it's identical
                target_path.unlink()
            else:
                logger.warning(f"Collision detected - different file exists: {target_path.name}")
                target_path = self._handle_collision(source_path, target_path)
        
        # Log operation (file path and hash only, no PHI)
        file_hash = self._compute_short_hash(source_path)
        logger.info(f"Renaming file: hash={file_hash}, target={target_path.name}")
        
        # Perform the rename/move
        shutil.move(str(source_path), str(target_path))
        
        logger.info(f"Rename complete: hash={file_hash}, success=true")
        
        return target_path

    def _handle_collision(self, source_path: Path, target_path: Path) -> Path:
        """
        Handle filename collision by appending a short hash.
        
        Args:
            source_path: Original source file (used for hash).
            target_path: Desired target path that already exists.
            
        Returns:
            New target path with hash suffix.
        """
        # Get short hash of source file content
        short_hash = self._compute_short_hash(source_path)
        
        # Insert hash before .pdf extension
        stem = target_path.stem
        new_filename = f"{stem}_{short_hash}.pdf"
        new_target = target_path.parent / new_filename
        
        # Handle rare case of hash collision too
        counter = 1
        while new_target.exists():
            new_filename = f"{stem}_{short_hash}_{counter}.pdf"
            new_target = target_path.parent / new_filename
            counter += 1
        
        logger.debug(f"Collision handled: using hash suffix {short_hash}")
        
        return new_target

    def _files_are_identical(self, file1: Path, file2: Path) -> bool:
        """
        Check if two files have identical content by comparing their hashes.
        
        Args:
            file1: First file path.
            file2: Second file path.
            
        Returns:
            True if files have identical content, False otherwise.
        """
        try:
            hash1 = self._compute_full_hash(file1)
            hash2 = self._compute_full_hash(file2)
            return hash1 == hash2
        except Exception as e:
            logger.warning(f"Error comparing files: {e}")
            return False
    
    def _compute_full_hash(self, file_path: Path) -> str:
        """
        Compute a full hash of file content for comparison.
        
        Returns:
            Full MD5 hex hash.
        """
        hasher = hashlib.md5()
        
        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def _compute_short_hash(self, file_path: Path) -> str:
        """
        Compute a short hash of file content.
        
        Returns:
            6-character hex hash.
        """
        return self._compute_full_hash(file_path)[:6]
