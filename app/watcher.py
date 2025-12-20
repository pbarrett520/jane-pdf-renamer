"""
Folder watcher for automatic PDF processing.

Watches a folder for new PDFs and processes them automatically.
"""

import logging
import time
from pathlib import Path
from typing import Optional, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from core import PDFExtractor, PatientInfoParser, FileRenamer

logger = logging.getLogger(__name__)


class PDFHandler(FileSystemEventHandler):
    """Handler for PDF file events."""
    
    def __init__(self, output_folder: Optional[Path] = None):
        super().__init__()
        self.output_folder = output_folder
        self.processed_files: Set[Path] = set()
        
        self.extractor = PDFExtractor()
        self.parser = PatientInfoParser()
        self.renamer = FileRenamer(output_folder=output_folder)
    
    def on_created(self, event):
        """Handle file creation event."""
        if not isinstance(event, FileCreatedEvent):
            return
        
        path = Path(event.src_path)
        
        # Only process PDFs
        if path.suffix.lower() != '.pdf':
            return
        
        # Skip if already processed
        if path in self.processed_files:
            return
        
        # Wait a moment for file to be fully written
        time.sleep(0.5)
        
        self.process_pdf(path)
    
    def process_pdf(self, pdf_path: Path):
        """Process a single PDF file."""
        if not pdf_path.exists():
            return
        
        logger.info(f"Processing: {pdf_path.name}")
        
        try:
            text = self.extractor.extract_text(pdf_path)
            # Pass filename for initials extraction
            info = self.parser.parse(text, filename=pdf_path.name)
            
            if info.needs_review():
                logger.warning(f"Low confidence for {pdf_path.name} - skipping (needs manual review)")
                return
            
            if not info.is_complete():
                logger.error(f"Cannot process {pdf_path.name} - missing required fields")
                return
            
            new_path = self.renamer.rename_file(pdf_path, info)
            self.processed_files.add(new_path)
            
            logger.info(f"Renamed to: {new_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_path.name}: {type(e).__name__}")


class FolderWatcher:
    """Watches a folder for new PDFs."""
    
    def __init__(self, watch_folder: Path, output_folder: Optional[Path] = None):
        self.watch_folder = watch_folder
        self.output_folder = output_folder
        self.observer = Observer()
        self.handler = PDFHandler(output_folder)
    
    def start(self):
        """Start watching the folder."""
        self.observer.schedule(
            self.handler,
            str(self.watch_folder),
            recursive=False
        )
        self.observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        
        self.observer.join()
    
    def run(self):
        """Alias for start() for backwards compatibility."""
        self.start()
    
    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()
