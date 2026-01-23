"""
Test suite for PDF extraction, parsing, and renaming.

TDD approach: These tests define the expected behavior before implementation.
The sample PDF in the repo root is used as the test fixture.
"""

import os
import hashlib
import shutil
import tempfile
from pathlib import Path
from datetime import date

import pytest

# Import will fail initially until implementation is complete
from core.extractor import PDFExtractor
from core.parser import PatientInfoParser, PatientInfo
from core.renamer import FileRenamer, FileFormat


# Path to the sample PDF fixture
FIXTURE_DIR = Path(__file__).parent.parent
SAMPLE_PDF = FIXTURE_DIR / "HealthStre_Chart_1_TP_20251218_88209-2.pdf"


class TestPDFExtractor:
    """Tests for PDF text extraction."""

    def test_extract_text_returns_string(self):
        """Extractor should return a string from PDF."""
        extractor = PDFExtractor()
        text = extractor.extract_text(SAMPLE_PDF)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_extract_text_contains_chart_keyword(self):
        """Extracted text should contain 'Chart' keyword."""
        extractor = PDFExtractor()
        text = extractor.extract_text(SAMPLE_PDF)
        assert "Chart" in text

    def test_extract_text_contains_patient_name(self):
        """Extracted text should contain patient display name."""
        extractor = PDFExtractor()
        text = extractor.extract_text(SAMPLE_PDF)
        assert "Test Patient" in text

    def test_extract_text_contains_date(self):
        """Extracted text should contain appointment date."""
        extractor = PDFExtractor()
        text = extractor.extract_text(SAMPLE_PDF)
        assert "December 18, 2025" in text

    def test_extract_text_nonexistent_file_raises(self):
        """Extractor should raise FileNotFoundError for missing file."""
        extractor = PDFExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract_text(Path("/nonexistent/file.pdf"))

    def test_extract_text_does_not_write_to_disk(self, tmp_path):
        """Ensure extraction doesn't create any files (HIPAA compliance)."""
        extractor = PDFExtractor()
        initial_files = set(tmp_path.iterdir())
        
        # Extract with a working directory set to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            extractor.extract_text(SAMPLE_PDF)
        finally:
            os.chdir(original_cwd)
        
        final_files = set(tmp_path.iterdir())
        assert initial_files == final_files, "Extraction should not write files to disk"


class TestPatientInfoParser:
    """Tests for parsing patient info from extracted text."""

    @pytest.fixture
    def sample_text(self):
        """Get extracted text from sample PDF."""
        extractor = PDFExtractor()
        return extractor.extract_text(SAMPLE_PDF)

    def test_parse_returns_patient_info(self, sample_text):
        """Parser should return a PatientInfo dataclass."""
        parser = PatientInfoParser()
        info = parser.parse(sample_text)
        assert isinstance(info, PatientInfo)

    def test_parse_extracts_first_name(self, sample_text):
        """Parser should extract 'Test' as first name."""
        parser = PatientInfoParser()
        info = parser.parse(sample_text)
        assert info.first_name == "Test"

    def test_parse_extracts_last_name(self, sample_text):
        """Parser should extract 'Patient' as last name."""
        parser = PatientInfoParser()
        info = parser.parse(sample_text)
        assert info.last_name == "Patient"

    def test_parse_extracts_date(self, sample_text):
        """Parser should extract December 18, 2025 as date."""
        parser = PatientInfoParser()
        info = parser.parse(sample_text)
        assert info.appointment_date == date(2025, 12, 18)

    def test_parse_strips_trailing_number_from_name(self):
        """Parser should strip trailing number from patient name."""
        parser = PatientInfoParser()
        # Simulate text with "Test Patient 1" after Chart
        text = "Chart\nTest Patient 1\nDecember 18, 2025"
        info = parser.parse(text)
        assert info.first_name == "Test"
        assert info.last_name == "Patient"

    def test_parse_handles_multi_word_first_name(self):
        """Parser should handle multi-word first names."""
        parser = PatientInfoParser()
        text = "Chart\nMary Jane Watson 2\nJanuary 1, 2024"
        info = parser.parse(text)
        assert info.first_name == "Mary Jane"
        assert info.last_name == "Watson"

    def test_parse_handles_empty_lines_after_chart(self):
        """Parser should skip empty lines after Chart."""
        parser = PatientInfoParser()
        text = "Chart\n\n\nTest Patient 1\nDecember 18, 2025"
        info = parser.parse(text)
        assert info.first_name == "Test"
        assert info.last_name == "Patient"

    def test_parse_confidence_high_when_all_fields_found(self, sample_text):
        """Parser should report high confidence when all fields found."""
        parser = PatientInfoParser()
        info = parser.parse(sample_text)
        assert info.confidence >= 0.9

    def test_parse_confidence_low_when_name_missing(self):
        """Parser should report low confidence when name missing."""
        parser = PatientInfoParser()
        text = "Some random text without patient info\nDecember 18, 2025"
        info = parser.parse(text)
        assert info.confidence <= 0.5

    def test_parse_confidence_low_when_date_missing(self):
        """Parser should report low confidence when date missing."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1\nNo date here"
        info = parser.parse(text)
        assert info.confidence <= 0.5

    def test_parse_various_date_formats(self):
        """Parser should handle various month name formats."""
        parser = PatientInfoParser()
        test_cases = [
            ("Chart\nJohn Doe 1\nJanuary 5, 2024", date(2024, 1, 5)),
            ("Chart\nJohn Doe 1\nFebruary 28, 2024", date(2024, 2, 28)),
            ("Chart\nJohn Doe 1\nMarch 15, 2024", date(2024, 3, 15)),
            ("Chart\nJohn Doe 1\nApril 1, 2024", date(2024, 4, 1)),
            ("Chart\nJohn Doe 1\nMay 20, 2024", date(2024, 5, 20)),
            ("Chart\nJohn Doe 1\nJune 30, 2024", date(2024, 6, 30)),
            ("Chart\nJohn Doe 1\nJuly 4, 2024", date(2024, 7, 4)),
            ("Chart\nJohn Doe 1\nAugust 15, 2024", date(2024, 8, 15)),
            ("Chart\nJohn Doe 1\nSeptember 21, 2024", date(2024, 9, 21)),
            ("Chart\nJohn Doe 1\nOctober 31, 2024", date(2024, 10, 31)),
            ("Chart\nJohn Doe 1\nNovember 11, 2024", date(2024, 11, 11)),
            ("Chart\nJohn Doe 1\nDecember 25, 2024", date(2024, 12, 25)),
        ]
        for text, expected_date in test_cases:
            info = parser.parse(text)
            assert info.appointment_date == expected_date, f"Failed for {text}"

    def test_parse_doi_in_patient_name(self):
        """Parser should extract DOI code from patient name."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1 (DOI:010125)\nDecember 18, 2025"
        # Use filename with initials to correctly split "Test" / "Patient 1"
        info = parser.parse(text, filename="HealthStre_Chart_1_TP_20251218_88209-2.pdf")
        assert info.date_code == "DOI010125"
        assert info.first_name == "Test"
        assert info.last_name == "Patient 1"  # Number preserved as part of compound name
        assert info.is_complete()

    def test_parse_dob_in_patient_name(self):
        """Parser should extract DOB code from patient name."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1 (DOB:031590)\nDecember 18, 2025"
        # Use filename with initials to correctly split "Test" / "Patient 1"
        info = parser.parse(text, filename="HealthStre_Chart_1_TP_20251218_88209-2.pdf")
        assert info.date_code == "DOB031590"
        assert info.first_name == "Test"
        assert info.last_name == "Patient 1"

    def test_parse_doi_with_space(self):
        """Parser should handle DOI with space after colon."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1 (DOI: 010125)\nDecember 18, 2025"
        info = parser.parse(text)
        assert info.date_code == "DOI010125"

    def test_parse_doi_case_insensitive(self):
        """Parser should handle lowercase doi/dob."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1 (doi:010125)\nDecember 18, 2025"
        info = parser.parse(text)
        assert info.date_code == "DOI010125"  # Normalized to uppercase

    def test_parse_no_doi_strips_trailing_number(self):
        """Without DOI/DOB, trailing number should still be stripped."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1\nDecember 18, 2025"
        info = parser.parse(text)
        assert info.date_code is None
        assert info.first_name == "Test"
        assert info.last_name == "Patient"  # Number stripped

    def test_parse_doi_with_initials(self):
        """Parser should use initials to split name correctly with DOI."""
        parser = PatientInfoParser()
        text = "Chart\nTest Patient 1 (DOI:010125)\nDecember 18, 2025"
        # Simulate filename with initials TP (Test, Patient 1)
        info = parser.parse(text, filename="HealthStre_Chart_1_TP_20251218_88209-2.pdf")
        assert info.first_name == "Test"
        assert info.last_name == "Patient 1"
        assert info.date_code == "DOI010125"


class TestFileRenamer:
    """Tests for file renaming logic."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory with a copy of the sample PDF."""
        pdf_copy = tmp_path / "test_input.pdf"
        shutil.copy(SAMPLE_PDF, pdf_copy)
        return tmp_path

    def test_generate_filename_format(self):
        """Generated filename should match expected format (MMDDYY)."""
        renamer = FileRenamer()
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        filename = renamer.generate_filename(info)
        assert filename == "Patient, Test 121825 PT Note.pdf"

    def test_generate_filename_exact_match_for_sample(self):
        """
        CRITICAL TEST: The exact expected output for the sample PDF.
        
        Input: HealthStre_Chart_1_TP_20251218_88209-2.pdf
        Expected output: Patient, Test 121825 PT Note.pdf
        """
        extractor = PDFExtractor()
        parser = PatientInfoParser()
        renamer = FileRenamer()

        text = extractor.extract_text(SAMPLE_PDF)
        info = parser.parse(text)
        filename = renamer.generate_filename(info)

        assert filename == "Patient, Test 121825 PT Note.pdf"

    def test_generate_filename_with_different_formats(self):
        """Test all available file formats."""
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        
        renamer = FileRenamer()
        
        # Test each format
        assert renamer.generate_filename(info, FileFormat.APPT_BILLING) == \
            "Patient, Test 121825 PT Note.pdf"
        assert renamer.generate_filename(info, FileFormat.APPT_BILLING_EVAL) == \
            "Patient, Test 121825 PT Eval Note.pdf"
        assert renamer.generate_filename(info, FileFormat.APPT_BILLING_PROGRESS) == \
            "Patient, Test 121825 PT Progress Note.pdf"
        assert renamer.generate_filename(info, FileFormat.APPT_BILLING_DISCHARGE) == \
            "Patient, Test 121825 PT Discharge Note.pdf"
        
        # Current discharge uses today's date - just verify format is correct
        today_str = date.today().strftime("%m%d%y")
        filename = renamer.generate_filename(info, FileFormat.CURRENT_DISCHARGE)
        assert filename == f"Patient, Test {today_str} PT Chart Note.pdf"

    def test_rename_file_creates_correct_name(self, temp_dir):
        """Renaming should create file with correct name."""
        renamer = FileRenamer()
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        source = temp_dir / "test_input.pdf"
        result = renamer.rename_file(source, info)
        
        expected_path = temp_dir / "Patient, Test 121825 PT Note.pdf"
        assert result == expected_path
        assert expected_path.exists()
        assert not source.exists()

    def test_rename_file_to_output_folder(self, temp_dir):
        """Renaming should move file to output folder if specified."""
        output_dir = temp_dir / "Processed"
        output_dir.mkdir()
        
        renamer = FileRenamer(output_folder=output_dir)
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        source = temp_dir / "test_input.pdf"
        result = renamer.rename_file(source, info)
        
        expected_path = output_dir / "Patient, Test 121825 PT Note.pdf"
        assert result == expected_path
        assert expected_path.exists()

    def test_rename_prevents_overwrite_with_hash(self, temp_dir):
        """Should append hash when target filename exists."""
        renamer = FileRenamer()
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        
        # Create existing file with target name
        existing = temp_dir / "Patient, Test 121825 PT Note.pdf"
        existing.write_bytes(b"existing content")
        
        source = temp_dir / "test_input.pdf"
        result = renamer.rename_file(source, info)
        
        # Should have hash suffix
        assert result.name.startswith("Patient, Test 121825 PT Note_")
        assert result.name.endswith(".pdf")
        assert result.exists()
        # Original target should still exist
        assert existing.exists()

    def test_rename_hash_is_short(self, temp_dir):
        """Hash suffix should be short (6-8 chars)."""
        renamer = FileRenamer()
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        
        existing = temp_dir / "Patient, Test 121825 PT Note.pdf"
        existing.write_bytes(b"existing")
        
        source = temp_dir / "test_input.pdf"
        result = renamer.rename_file(source, info)
        
        # Extract hash from filename
        stem = result.stem  # "Patient, Test 121825 PT Note_HASH"
        hash_part = stem.split("_")[-1]
        assert 6 <= len(hash_part) <= 8

    def test_generate_filename_with_doi_code(self):
        """Filename should use DOI code instead of date when present."""
        renamer = FileRenamer(file_format=FileFormat.CURRENT_DISCHARGE)
        info = PatientInfo(
            first_name="Test",
            last_name="Patient 1",
            appointment_date=date(2025, 12, 18),
            confidence=1.0,
            date_code="DOI010125"
        )
        filename = renamer.generate_filename(info)
        assert filename == "Patient 1, Test DOI010125 PT Chart Note.pdf"

    def test_generate_filename_with_dob_code(self):
        """Filename should use DOB code instead of date when present."""
        renamer = FileRenamer(file_format=FileFormat.APPT_BILLING)
        info = PatientInfo(
            first_name="Jane",
            last_name="Doe 2",
            appointment_date=date(2025, 12, 18),
            confidence=1.0,
            date_code="DOB031590"
        )
        filename = renamer.generate_filename(info)
        assert filename == "Doe 2, Jane DOB031590 PT Note.pdf"

    def test_generate_filename_prefers_date_code_over_appointment_date(self):
        """DOI/DOB code should take precedence over appointment date."""
        renamer = FileRenamer()
        info = PatientInfo(
            first_name="Test",
            last_name="Patient 1",
            appointment_date=date(2025, 12, 18),  # Would be 121825
            confidence=1.0,
            date_code="DOI010125"  # Should use this instead
        )
        filename = renamer.generate_filename(info)
        assert "DOI010125" in filename
        assert "121825" not in filename
    
    def test_rename_identical_file_replaces_without_hash(self, temp_dir):
        """Renaming an identical file should replace it without adding hash."""
        renamer = FileRenamer(output_folder=temp_dir)
        info = PatientInfo(
            first_name="Test",
            last_name="Patient",
            appointment_date=date(2025, 12, 18),
            confidence=1.0
        )
        
        # Use the test_input.pdf from temp_dir
        first_source = temp_dir / "test_input.pdf"
        
        # Process file first time
        first_result = renamer.rename_file(first_source, info)
        expected_name = first_result.name
        
        # Make a copy of the same file to process again
        second_source = temp_dir / "source_copy.pdf"
        shutil.copy(SAMPLE_PDF, second_source)
        
        # Process identical file again
        second_result = renamer.rename_file(second_source, info)
        
        # Should have the same name (no hash added for identical file)
        assert second_result.name == expected_name
        
        # Should only have one file in output directory named with patient info
        patient_files = list(temp_dir.glob("Patient, Test *.pdf"))
        assert len(patient_files) == 1


class TestEndToEndProcessing:
    """End-to-end integration tests."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temp directory with sample PDF copy."""
        pdf_copy = tmp_path / "input.pdf"
        shutil.copy(SAMPLE_PDF, pdf_copy)
        return tmp_path

    def test_full_pipeline_exact_output(self, temp_dir):
        """
        CRITICAL: Full pipeline test with exact expected output.
        
        This is the primary acceptance test for the application.
        """
        from core import PDFExtractor, PatientInfoParser, FileRenamer

        source = temp_dir / "input.pdf"
        
        # Run full pipeline
        extractor = PDFExtractor()
        parser = PatientInfoParser()
        renamer = FileRenamer()

        text = extractor.extract_text(source)
        info = parser.parse(text)
        result = renamer.rename_file(source, info)

        # Verify exact output filename
        assert result.name == "Patient, Test 121825 PT Note.pdf"
        assert result.exists()
        assert not source.exists()

    def test_pipeline_with_output_folder(self, temp_dir):
        """Pipeline should work with configured output folder."""
        from core import PDFExtractor, PatientInfoParser, FileRenamer

        source = temp_dir / "input.pdf"
        output_dir = temp_dir / "Processed"
        output_dir.mkdir()

        extractor = PDFExtractor()
        parser = PatientInfoParser()
        renamer = FileRenamer(output_folder=output_dir)

        text = extractor.extract_text(source)
        info = parser.parse(text)
        result = renamer.rename_file(source, info)

        assert result.parent == output_dir
        assert result.name == "Patient, Test 121825 PT Note.pdf"


class TestHIPAACompliance:
    """Tests to verify HIPAA compliance requirements."""

    def test_no_phi_in_logs(self, caplog, temp_dir, tmp_path):
        """Our own logs should not contain patient names or extracted text.
        
        Note: Third-party libraries like pdfminer may log PDF content for debugging,
        but our own application code should not log PHI.
        """
        import logging
        from core import PDFExtractor, PatientInfoParser, FileRenamer

        # Copy sample PDF
        source = tmp_path / "test.pdf"
        shutil.copy(SAMPLE_PDF, source)

        # Enable logging capture only for our modules
        with caplog.at_level(logging.DEBUG, logger="core"):
            extractor = PDFExtractor()
            parser = PatientInfoParser()
            renamer = FileRenamer()

            text = extractor.extract_text(source)
            info = parser.parse(text)
            renamer.rename_file(source, info)

        # Check OUR logs don't contain PHI (filter to only core.* loggers)
        our_logs = [record for record in caplog.records if record.name.startswith("core")]
        our_log_text = " ".join(record.message.lower() for record in our_logs)
        
        assert "test patient" not in our_log_text, "Patient name should not be in logs"
        # File path and hash are allowed
        # Success/failure codes are allowed

    def test_extractor_does_not_cache_text(self):
        """Extractor should not retain extracted text in memory after return."""
        extractor = PDFExtractor()
        text = extractor.extract_text(SAMPLE_PDF)
        
        # Extractor should not have instance variables storing text
        assert not hasattr(extractor, '_cached_text')
        assert not hasattr(extractor, 'last_text')
        assert not hasattr(extractor, 'text')


# Fixture to make SAMPLE_PDF available
@pytest.fixture
def temp_dir(tmp_path):
    """Generic temp directory fixture."""
    return tmp_path
