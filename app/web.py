"""
FastAPI web server for Jane PDF Renamer.

Browser-based GUI with drag-and-drop and format selection.
"""

import hashlib
import logging
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core import PDFExtractor, PatientInfoParser, PatientInfo, FileFormat
from core.renamer import FileRenamer

logger = logging.getLogger(__name__)

# Paths
APP_DIR = Path(__file__).parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

# Create FastAPI app
app = FastAPI(title="Jane PDF Renamer", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


class ProcessResult(BaseModel):
    """Result of processing a PDF."""
    success: bool
    original_name: str
    new_name: Optional[str] = None
    new_path: Optional[str] = None
    error: Optional[str] = None
    needs_review: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_str: Optional[str] = None
    confidence: float = 0.0


def process_pdf(
    file_path: Path,
    file_format: FileFormat,
    output_folder: Optional[Path] = None,
    original_filename: Optional[str] = None
) -> ProcessResult:
    """Process a single PDF file."""
    extractor = PDFExtractor()
    parser = PatientInfoParser()
    
    # Use original filename for initials extraction, fall back to current filename
    filename_for_parsing = original_filename or file_path.name
    
    try:
        # Extract and parse
        text = extractor.extract_text(file_path)
        info = parser.parse(text, filename=filename_for_parsing)
        
        # Check confidence
        if info.confidence < 0.8 or not info.first_name or not info.last_name:
            return ProcessResult(
                success=False,
                original_name=file_path.name,
                needs_review=True,
                first_name=info.first_name or "",
                last_name=info.last_name or "",
                date_str=info.appointment_date.strftime("%m%d%y") if info.appointment_date else "",
                confidence=info.confidence,
            )
        
        # Create renamer with output folder and format
        renamer = FileRenamer(output_folder=output_folder, file_format=file_format)
        
        # Rename the file
        result_path = renamer.rename_file(file_path, info)
        
        return ProcessResult(
            success=True,
            original_name=file_path.name,
            new_name=result_path.name,
            new_path=str(result_path),
            confidence=info.confidence,
        )
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return ProcessResult(
            success=False,
            original_name=file_path.name,
            error=str(e),
        )


# Store uploaded files temporarily
UPLOAD_DIR = Path(tempfile.gettempdir()) / "jane-pdf-renamer"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main application page."""
    default_output = str(UPLOAD_DIR / "Processed")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "default_output": default_output}
    )


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    format_type: str = Form("appt_billing"),
    output_folder: str = Form(""),
):
    """Handle file upload and processing."""
    # Preserve original filename for initials extraction
    original_filename = file.filename
    
    # Save uploaded file temporarily
    temp_path = UPLOAD_DIR / file.filename
    
    try:
        content = await file.read()
        temp_path.write_bytes(content)
        
        # Parse format
        try:
            file_format = FileFormat(format_type)
        except ValueError:
            file_format = FileFormat.APPT_BILLING
        
        # Determine output folder
        # If none specified, use a "Processed" folder in temp dir
        if output_folder:
            output_path = Path(output_folder)
        else:
            output_path = UPLOAD_DIR / "Processed"
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process - pass original filename for initials extraction
        result = process_pdf(temp_path, file_format, output_path, original_filename=original_filename)
        
        return JSONResponse(content=result.model_dump())
        
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e), "original_name": file.filename},
            status_code=500
        )


@app.post("/rename-manual")
async def rename_manual(
    filename: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    date_str: str = Form(...),
    format_type: str = Form("appt_billing"),
    output_folder: str = Form(""),
):
    """Handle manual rename with user-provided info."""
    temp_path = UPLOAD_DIR / filename
    
    if not temp_path.exists():
        return JSONResponse(
            content={"success": False, "error": "File not found"},
            status_code=404
        )
    
    try:
        # Parse format
        try:
            file_format = FileFormat(format_type)
        except ValueError:
            file_format = FileFormat.APPT_BILLING
        
        # Determine output folder
        if output_folder:
            output_path = Path(output_folder)
        else:
            output_path = UPLOAD_DIR / "Processed"
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Parse the date - try MMDDYY format first
        try:
            target_date = datetime.strptime(date_str, "%m%d%y").date()
        except ValueError:
            try:
                target_date = datetime.strptime(date_str, "%m/%d/%y").date()
            except ValueError:
                target_date = date.today()
        
        # Create PatientInfo manually
        info = PatientInfo(
            first_name=first_name,
            last_name=last_name,
            appointment_date=target_date,
            confidence=1.0  # User confirmed
        )
        
        # Create renamer and rename
        renamer = FileRenamer(output_folder=output_path, file_format=file_format)
        result_path = renamer.rename_file(temp_path, info)
        
        return JSONResponse(content={
            "success": True,
            "original_name": filename,
            "new_name": result_path.name,
            "new_path": str(result_path),
        })
        
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )


@app.get("/download/{filename:path}")
async def download_file(filename: str):
    """Download a processed file for the browser to save to selected directory."""
    # Look for the file in the processed folder
    processed_dir = UPLOAD_DIR / "Processed"
    file_path = processed_dir / filename
    
    if not file_path.exists():
        # Also check the temp upload dir
        file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        return JSONResponse(
            content={"error": "File not found"},
            status_code=404
        )
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf"
    )


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
