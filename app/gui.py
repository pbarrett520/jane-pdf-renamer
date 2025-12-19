"""
PySide6 GUI for Jane PDF Renamer.

Provides drag-and-drop interface for renaming PDFs.
"""

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QDateEdit,
    QFrame,
    QFileDialog,
    QProgressBar,
)

from core import PDFExtractor, PatientInfoParser, PatientInfo, FileRenamer

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single PDF."""
    source_path: Path
    success: bool
    new_path: Optional[Path] = None
    error_message: Optional[str] = None
    needs_review: bool = False
    info: Optional[PatientInfo] = None


class ProcessingWorker(QThread):
    """Background worker for PDF processing."""
    
    progress = Signal(int, int)  # current, total
    result = Signal(ProcessingResult)
    finished_all = Signal()
    
    def __init__(self, files: List[Path], output_folder: Optional[Path] = None):
        super().__init__()
        self.files = files
        self.output_folder = output_folder
        self._cancelled = False
    
    def run(self):
        """Process files in background."""
        extractor = PDFExtractor()
        parser = PatientInfoParser()
        renamer = FileRenamer(output_folder=self.output_folder)
        
        for i, pdf_path in enumerate(self.files):
            if self._cancelled:
                break
            
            self.progress.emit(i + 1, len(self.files))
            
            try:
                text = extractor.extract_text(pdf_path)
                info = parser.parse(text)
                
                if info.needs_review():
                    result = ProcessingResult(
                        source_path=pdf_path,
                        success=False,
                        needs_review=True,
                        info=info,
                        error_message="Needs manual review"
                    )
                else:
                    new_path = renamer.rename_file(pdf_path, info)
                    result = ProcessingResult(
                        source_path=pdf_path,
                        success=True,
                        new_path=new_path,
                        info=info
                    )
                    
            except Exception as e:
                result = ProcessingResult(
                    source_path=pdf_path,
                    success=False,
                    error_message=str(e)
                )
            
            self.result.emit(result)
        
        self.finished_all.emit()
    
    def cancel(self):
        """Cancel processing."""
        self._cancelled = True


class ReviewDialog(QDialog):
    """Dialog for reviewing and editing patient info before renaming."""
    
    def __init__(self, pdf_path: Path, info: PatientInfo, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.info = info
        self.result_info: Optional[PatientInfo] = None
        
        self.setWindowTitle("Review Patient Information")
        self.setMinimumWidth(450)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        # File info
        file_label = QLabel(f"<b>File:</b> {self.pdf_path.name}")
        file_label.setWordWrap(True)
        layout.addWidget(file_label)
        
        layout.addSpacing(10)
        
        # Form for editing
        form = QFormLayout()
        
        self.first_name_edit = QLineEdit(self.info.first_name)
        self.first_name_edit.setPlaceholderText("First name")
        form.addRow("First Name:", self.first_name_edit)
        
        self.last_name_edit = QLineEdit(self.info.last_name)
        self.last_name_edit.setPlaceholderText("Last name")
        form.addRow("Last Name:", self.last_name_edit)
        
        self.date_edit = QDateEdit()
        if self.info.appointment_date:
            self.date_edit.setDate(self.info.appointment_date)
        else:
            self.date_edit.setDate(date.today())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("MMMM d, yyyy")
        form.addRow("Appointment Date:", self.date_edit)
        
        layout.addLayout(form)
        
        layout.addSpacing(10)
        
        # Preview
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.StyledPanel)
        preview_layout = QVBoxLayout(preview_frame)
        
        preview_title = QLabel("<b>Output Filename Preview:</b>")
        preview_layout.addWidget(preview_title)
        
        self.preview_label = QLabel()
        self.preview_label.setFont(QFont("monospace"))
        self.preview_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_frame)
        
        # Connect signals for live preview
        self.first_name_edit.textChanged.connect(self.update_preview)
        self.last_name_edit.textChanged.connect(self.update_preview)
        self.date_edit.dateChanged.connect(self.update_preview)
        self.update_preview()
        
        layout.addSpacing(10)
        
        # Buttons
        buttons = QHBoxLayout()
        
        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self.reject)
        buttons.addWidget(skip_btn)
        
        buttons.addStretch()
        
        rename_btn = QPushButton("Rename")
        rename_btn.setDefault(True)
        rename_btn.clicked.connect(self.accept_rename)
        buttons.addWidget(rename_btn)
        
        layout.addLayout(buttons)
    
    def update_preview(self):
        """Update the filename preview."""
        first = self.first_name_edit.text().strip()
        last = self.last_name_edit.text().strip()
        dt = self.date_edit.date().toPython()
        
        if first and last:
            date_str = dt.strftime("%m-%d-%Y")
            filename = f"{last}, {first} {date_str} PT Note.pdf"
        else:
            filename = "(Enter first and last name)"
        
        self.preview_label.setText(filename)
    
    def accept_rename(self):
        """Accept and store the edited info."""
        first = self.first_name_edit.text().strip()
        last = self.last_name_edit.text().strip()
        dt = self.date_edit.date().toPython()
        
        if not first or not last:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter both first and last name."
            )
            return
        
        self.result_info = PatientInfo(
            first_name=first,
            last_name=last,
            appointment_date=dt,
            confidence=1.0
        )
        self.accept()


class ResultItem(QFrame):
    """Widget for displaying a single processing result."""
    
    def __init__(self, result: ProcessingResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the result item UI."""
        self.setFrameShape(QFrame.StyledPanel)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        
        # Status icon
        if self.result.success:
            icon = "✅"
        elif self.result.needs_review:
            icon = "⚠️"
        else:
            icon = "❌"
        
        icon_label = QLabel(icon)
        icon_label.setFixedWidth(24)
        layout.addWidget(icon_label)
        
        # File info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        source_name = self.result.source_path.name
        if len(source_name) > 50:
            source_name = source_name[:47] + "..."
        
        if self.result.success:
            text = f"<b>{self.result.new_path.name}</b>"
            info_layout.addWidget(QLabel(text))
            info_layout.addWidget(QLabel(f"<small>from: {source_name}</small>"))
        elif self.result.needs_review:
            text = f"<b>{source_name}</b> - Needs review"
            info_layout.addWidget(QLabel(text))
        else:
            text = f"<b>{source_name}</b>"
            info_layout.addWidget(QLabel(text))
            info_layout.addWidget(QLabel(f"<small style='color: red;'>{self.result.error_message}</small>"))
        
        layout.addLayout(info_layout, stretch=1)


class DropZone(QFrame):
    """Drop zone widget for drag-and-drop."""
    
    files_dropped = Signal(list)  # List[Path]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(400, 200)
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the drop zone UI."""
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            DropZone {
                border: 2px dashed #888;
                border-radius: 12px;
                background-color: #f8f9fa;
            }
            DropZone:hover {
                border-color: #4a90d9;
                background-color: #e8f4fd;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        
        text = QLabel("Drag & Drop PDFs Here")
        text.setStyleSheet("font-size: 18px; font-weight: bold; color: #555;")
        text.setAlignment(Qt.AlignCenter)
        layout.addWidget(text)
        
        subtext = QLabel("or click to browse")
        subtext.setStyleSheet("font-size: 12px; color: #888;")
        subtext.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtext)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            # Check if any URL is a PDF
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    self.setStyleSheet("""
                        DropZone {
                            border: 2px solid #4a90d9;
                            border-radius: 12px;
                            background-color: #e8f4fd;
                        }
                    """)
                    return
    
    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setup_ui()  # Reset style
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        self.setup_ui()  # Reset style
        
        files = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == '.pdf' and path.exists():
                files.append(path)
        
        if files:
            self.files_dropped.emit(files)
    
    def mousePressEvent(self, event):
        """Handle click to browse."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files",
            "",
            "PDF Files (*.pdf)"
        )
        if files:
            self.files_dropped.emit([Path(f) for f in files])


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jane PDF Renamer")
        self.setMinimumSize(600, 500)
        
        self.output_folder: Optional[Path] = None
        self.worker: Optional[ProcessingWorker] = None
        self.pending_reviews: List[ProcessingResult] = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the main window UI."""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Jane PDF Renamer")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Rename patient chart PDFs automatically")
        subtitle.setStyleSheet("font-size: 12px; color: #666;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.process_files)
        layout.addWidget(self.drop_zone)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Results area
        results_container = QWidget()
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_label = QLabel("Processed Files:")
        self.results_label.setStyleSheet("font-weight: bold;")
        self.results_label.hide()
        results_layout.addWidget(self.results_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(150)
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_layout.setSpacing(5)
        
        scroll.setWidget(self.results_widget)
        results_layout.addWidget(scroll)
        
        layout.addWidget(results_container)
        
        # Output folder button
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output: Rename in place")
        self.output_label.setStyleSheet("color: #666;")
        output_layout.addWidget(self.output_label)
        
        output_btn = QPushButton("Change Output Folder...")
        output_btn.clicked.connect(self.select_output_folder)
        output_layout.addWidget(output_btn)
        
        layout.addLayout(output_layout)
    
    def select_output_folder(self):
        """Open dialog to select output folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder"
        )
        if folder:
            self.output_folder = Path(folder)
            self.output_label.setText(f"Output: {folder}")
        else:
            self.output_folder = None
            self.output_label.setText("Output: Rename in place")
    
    def process_files(self, files: List[Path]):
        """Process the dropped files."""
        if not files:
            return
        
        # Show progress
        self.progress_bar.show()
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setValue(0)
        
        self.results_label.show()
        
        # Clear previous results
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.pending_reviews = []
        
        # Start worker
        self.worker = ProcessingWorker(files, self.output_folder)
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(self.on_result)
        self.worker.finished_all.connect(self.on_finished)
        self.worker.start()
    
    def on_progress(self, current: int, total: int):
        """Handle progress update."""
        self.progress_bar.setValue(current)
    
    def on_result(self, result: ProcessingResult):
        """Handle single file result."""
        if result.needs_review:
            self.pending_reviews.append(result)
        
        item = ResultItem(result)
        self.results_layout.addWidget(item)
    
    def on_finished(self):
        """Handle all files finished."""
        self.progress_bar.hide()
        
        # Process pending reviews
        for result in self.pending_reviews:
            self.show_review_dialog(result)
    
    def show_review_dialog(self, result: ProcessingResult):
        """Show review dialog for a file that needs manual input."""
        if not result.info:
            return
        
        dialog = ReviewDialog(result.source_path, result.info, self)
        if dialog.exec() and dialog.result_info:
            # Rename with edited info
            try:
                renamer = FileRenamer(output_folder=self.output_folder)
                new_path = renamer.rename_file(result.source_path, dialog.result_info)
                
                # Update the result item
                result.success = True
                result.new_path = new_path
                result.needs_review = False
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"Renamed to: {new_path.name}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to rename: {e}"
                )

