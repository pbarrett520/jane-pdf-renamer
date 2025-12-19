"""
FastAPI web server for Jane PDF Renamer.

Browser-based GUI with drag-and-drop and format selection.
"""

import hashlib
import logging
import os
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from core import PDFExtractor, PatientInfoParser, PatientInfo, FileFormat
from core.renamer import FileRenamer

logger = logging.getLogger(__name__)

app = FastAPI(title="Jane PDF Renamer", version="1.0.0")


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
    output_folder: Optional[Path] = None
) -> ProcessResult:
    """Process a single PDF file."""
    extractor = PDFExtractor()
    parser = PatientInfoParser()
    
    try:
        # Extract and parse
        text = extractor.extract_text(file_path)
        info = parser.parse(text)
        
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
async def index():
    """Serve the main application page."""
    return get_html_template()


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    format_type: str = Form("appt_billing"),
    output_folder: str = Form(""),
):
    """Handle file upload and processing."""
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
        # If none specified, use a "Processed" folder in user's Downloads
        if output_folder:
            output_path = Path(output_folder)
        else:
            # Default to temp dir for processed files (user can copy from there)
            output_path = UPLOAD_DIR / "Processed"
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process
        result = process_pdf(temp_path, file_format, output_path)
        
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


def get_html_template() -> str:
    """Return the HTML template for the application."""
    # Get default output path for display
    default_output = str(UPLOAD_DIR / "Processed")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jane PDF Renamer</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0a0a0f;
            --bg-card: #12121a;
            --bg-hover: #1a1a25;
            --accent-primary: #00d4aa;
            --accent-secondary: #7c3aed;
            --accent-warning: #f59e0b;
            --accent-error: #ef4444;
            --text-primary: #f0f0f5;
            --text-secondary: #8888a0;
            --border-color: #2a2a3a;
            --success-bg: #0d3d30;
            --error-bg: #3d1515;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem;
            background-image: 
                radial-gradient(ellipse at 20% 20%, rgba(124, 58, 237, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(0, 212, 170, 0.08) 0%, transparent 50%);
        }}
        
        .container {{
            max-width: 720px;
            width: 100%;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        
        h1 {{
            font-family: 'Space Mono', monospace;
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }}
        
        .hipaa-badge {{
            background: var(--success-bg);
            color: var(--accent-primary);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        
        .card-title {{
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* Format selector */
        .format-options {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        
        .format-option {{
            display: flex;
            align-items: center;
            padding: 0.75rem 1rem;
            background: var(--bg-dark);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .format-option:hover {{
            border-color: var(--accent-primary);
            background: var(--bg-hover);
        }}
        
        .format-option.selected {{
            border-color: var(--accent-primary);
            background: rgba(0, 212, 170, 0.1);
        }}
        
        .format-option input[type="radio"] {{
            display: none;
        }}
        
        .radio-circle {{
            width: 18px;
            height: 18px;
            border: 2px solid var(--border-color);
            border-radius: 50%;
            margin-right: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }}
        
        .format-option.selected .radio-circle {{
            border-color: var(--accent-primary);
        }}
        
        .radio-circle::after {{
            content: '';
            width: 8px;
            height: 8px;
            background: var(--accent-primary);
            border-radius: 50%;
            opacity: 0;
            transition: opacity 0.2s ease;
        }}
        
        .format-option.selected .radio-circle::after {{
            opacity: 1;
        }}
        
        .format-label {{
            font-family: 'Space Mono', monospace;
            font-size: 0.8rem;
            color: var(--text-primary);
        }}
        
        .format-type {{
            font-size: 0.7rem;
            color: var(--text-secondary);
            padding: 0.15rem 0.4rem;
            background: var(--bg-hover);
            border-radius: 4px;
            margin-left: auto;
        }}
        
        .format-type.current {{
            background: rgba(245, 158, 11, 0.2);
            color: var(--accent-warning);
        }}
        
        .format-type.appt {{
            background: rgba(124, 58, 237, 0.2);
            color: var(--accent-secondary);
        }}
        
        /* Drop zone */
        .drop-zone {{
            border: 2px dashed var(--border-color);
            border-radius: 12px;
            padding: 3rem 2rem;
            text-align: center;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }}
        
        .drop-zone::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(0, 212, 170, 0.05), rgba(124, 58, 237, 0.05));
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .drop-zone:hover::before,
        .drop-zone.drag-over::before {{
            opacity: 1;
        }}
        
        .drop-zone:hover,
        .drop-zone.drag-over {{
            border-color: var(--accent-primary);
        }}
        
        .drop-zone-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.7;
        }}
        
        .drop-zone-text {{
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
        }}
        
        .drop-zone-hint {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        
        #file-input {{
            display: none;
        }}
        
        /* Results */
        .results-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .result-item {{
            display: flex;
            align-items: flex-start;
            padding: 1rem;
            background: var(--bg-dark);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            gap: 1rem;
        }}
        
        .result-item.success {{
            border-color: var(--accent-primary);
            background: var(--success-bg);
        }}
        
        .result-item.error {{
            border-color: var(--accent-error);
            background: var(--error-bg);
        }}
        
        .result-item.review {{
            border-color: var(--accent-warning);
            background: rgba(245, 158, 11, 0.1);
        }}
        
        .result-icon {{
            font-size: 1.5rem;
        }}
        
        .result-info {{
            flex: 1;
            min-width: 0;
        }}
        
        .result-original {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
        }}
        
        .result-new {{
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-primary);
            word-break: break-all;
        }}
        
        .result-path {{
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
            word-break: break-all;
        }}
        
        /* Review form */
        .review-form {{
            display: none;
            margin-top: 1rem;
            padding: 1rem;
            background: var(--bg-dark);
            border-radius: 8px;
        }}
        
        .review-form.visible {{
            display: block;
        }}
        
        .form-row {{
            display: flex;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }}
        
        .form-group {{
            flex: 1;
        }}
        
        .form-group label {{
            display: block;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .form-group input {{
            width: 100%;
            padding: 0.6rem 0.8rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-family: 'Space Mono', monospace;
            font-size: 0.9rem;
        }}
        
        .form-group input:focus {{
            outline: none;
            border-color: var(--accent-primary);
        }}
        
        .btn {{
            padding: 0.6rem 1.2rem;
            border: none;
            border-radius: 6px;
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .btn-primary {{
            background: var(--accent-primary);
            color: var(--bg-dark);
        }}
        
        .btn-primary:hover {{
            background: #00eebb;
            transform: translateY(-1px);
        }}
        
        /* Output folder */
        .output-section {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        .output-path {{
            flex: 1;
            font-family: 'Space Mono', monospace;
            font-size: 0.8rem;
            color: var(--text-secondary);
            padding: 0.5rem 0.75rem;
            background: var(--bg-dark);
            border-radius: 6px;
            border: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .output-path input {{
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-family: inherit;
            font-size: inherit;
            min-width: 0;
        }}
        
        .output-path input:focus {{
            outline: none;
        }}
        
        .output-path input::placeholder {{
            color: var(--text-secondary);
        }}
        
        .btn-browse {{
            display: flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.5rem 1rem;
            background: var(--accent-secondary);
            color: white;
            border: none;
            border-radius: 6px;
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }}
        
        .btn-browse:hover {{
            background: #8b5cf6;
            transform: translateY(-1px);
        }}
        
        .btn-browse:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}
        
        .folder-display {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.6rem 1rem;
            background: var(--bg-dark);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            flex: 1;
            min-width: 0;
        }}
        
        .folder-icon {{
            font-size: 1.2rem;
        }}
        
        .folder-name {{
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-primary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .folder-name.placeholder {{
            color: var(--text-secondary);
            font-style: italic;
        }}
        
        /* Loading state */
        .loading {{
            display: none;
            text-align: center;
            padding: 2rem;
        }}
        
        .loading.visible {{
            display: block;
        }}
        
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid var(--border-color);
            border-top-color: var(--accent-primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Footer */
        footer {{
            margin-top: auto;
            padding-top: 2rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.75rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚕️ Jane PDF Renamer</h1>
            <p class="subtitle">
                Medical Chart PDF Automation
                <span class="hipaa-badge">HIPAA COMPLIANT</span>
            </p>
        </header>
        
        <!-- Format Selection -->
        <div class="card">
            <h2 class="card-title">📋 Select Output Format</h2>
            <div class="format-options" id="format-options">
                <label class="format-option" data-format="current_discharge">
                    <input type="radio" name="format" value="current_discharge">
                    <span class="radio-circle"></span>
                    <span class="format-label">Last, First MMDDYY PT Chart Note.pdf</span>
                    <span class="format-type current">TODAY</span>
                </label>
                <label class="format-option selected" data-format="appt_billing">
                    <input type="radio" name="format" value="appt_billing" checked>
                    <span class="radio-circle"></span>
                    <span class="format-label">Last, First MMDDYY PT Note.pdf</span>
                    <span class="format-type appt">APPT DATE</span>
                </label>
                <label class="format-option" data-format="appt_billing_eval">
                    <input type="radio" name="format" value="appt_billing_eval">
                    <span class="radio-circle"></span>
                    <span class="format-label">Last, First MMDDYY PT Eval Note.pdf</span>
                    <span class="format-type appt">APPT DATE</span>
                </label>
                <label class="format-option" data-format="appt_billing_progress">
                    <input type="radio" name="format" value="appt_billing_progress">
                    <span class="radio-circle"></span>
                    <span class="format-label">Last, First MMDDYY PT Progress Note.pdf</span>
                    <span class="format-type appt">APPT DATE</span>
                </label>
                <label class="format-option" data-format="appt_billing_discharge">
                    <input type="radio" name="format" value="appt_billing_discharge">
                    <span class="radio-circle"></span>
                    <span class="format-label">Last, First MMDDYY PT Discharge Note.pdf</span>
                    <span class="format-type appt">APPT DATE</span>
                </label>
            </div>
        </div>
        
        <!-- Drop Zone -->
        <div class="card">
            <h2 class="card-title">📄 Upload PDF</h2>
            <div class="drop-zone" id="drop-zone">
                <div class="drop-zone-icon">📁</div>
                <p class="drop-zone-text">Drop PDF files here</p>
                <p class="drop-zone-hint">or click to browse</p>
            </div>
            <input type="file" id="file-input" accept=".pdf" multiple>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Processing PDF...</p>
            </div>
        </div>
        
        <!-- Results -->
        <div class="card" id="results-card" style="display: none;">
            <h2 class="card-title">✨ Results</h2>
            <div class="results-list" id="results-list"></div>
        </div>
        
        <!-- Review Form (shown when needed) -->
        <div class="card review-form" id="review-form">
            <h2 class="card-title">⚠️ Manual Review Required</h2>
            <p style="color: var(--text-secondary); margin-bottom: 1rem; font-size: 0.85rem;">
                Could not extract all information automatically. Please verify:
            </p>
            <input type="hidden" id="review-filename">
            <div class="form-row">
                <div class="form-group">
                    <label for="review-first">First Name</label>
                    <input type="text" id="review-first" placeholder="First">
                </div>
                <div class="form-group">
                    <label for="review-last">Last Name</label>
                    <input type="text" id="review-last" placeholder="Last">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label for="review-date">Date (MMDDYY)</label>
                    <input type="text" id="review-date" placeholder="121825">
                </div>
            </div>
            <button class="btn btn-primary" id="review-submit">Rename File</button>
        </div>
        
        <!-- Output Folder -->
        <div class="card">
            <h2 class="card-title">📂 Output Folder</h2>
            <div class="output-section">
                <div class="folder-display" id="folder-display">
                    <span class="folder-icon">📁</span>
                    <span class="folder-name" id="folder-name">{default_output}</span>
                </div>
                <button class="btn-browse" id="btn-browse" title="Choose output folder">
                    <span>📂</span> Browse
                </button>
            </div>
            <input type="hidden" id="output-folder" value="{default_output}">
            <p style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 0.75rem;" id="folder-hint">
                Click "Browse" to choose where renamed files will be saved.
            </p>
        </div>
    </div>
    
    <footer>
        <p>🔒 All processing happens locally. No data leaves your machine.</p>
    </footer>
    
    <script>
        // Format selection
        const formatOptions = document.querySelectorAll('.format-option');
        let selectedFormat = 'appt_billing';
        
        formatOptions.forEach(option => {{
            option.addEventListener('click', () => {{
                formatOptions.forEach(o => o.classList.remove('selected'));
                option.classList.add('selected');
                option.querySelector('input').checked = true;
                selectedFormat = option.dataset.format;
            }});
        }});
        
        // Drop zone functionality
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const loading = document.getElementById('loading');
        const resultsCard = document.getElementById('results-card');
        const resultsList = document.getElementById('results-list');
        const reviewForm = document.getElementById('review-form');
        
        dropZone.addEventListener('click', () => fileInput.click());
        
        dropZone.addEventListener('dragover', (e) => {{
            e.preventDefault();
            dropZone.classList.add('drag-over');
        }});
        
        dropZone.addEventListener('dragleave', () => {{
            dropZone.classList.remove('drag-over');
        }});
        
        dropZone.addEventListener('drop', (e) => {{
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            handleFiles(files);
        }});
        
        fileInput.addEventListener('change', (e) => {{
            handleFiles(e.target.files);
        }});
        
        async function handleFiles(files) {{
            loading.classList.add('visible');
            resultsCard.style.display = 'none';
            resultsList.innerHTML = '';
            reviewForm.classList.remove('visible');
            
            const outputFolder = document.getElementById('output-folder').value;
            
            for (const file of files) {{
                if (!file.name.toLowerCase().endsWith('.pdf')) {{
                    addResult({{
                        success: false,
                        original_name: file.name,
                        error: 'Not a PDF file'
                    }});
                    continue;
                }}
                
                const formData = new FormData();
                formData.append('file', file);
                formData.append('format_type', selectedFormat);
                formData.append('output_folder', outputFolder);
                
                try {{
                    const response = await fetch('/upload', {{
                        method: 'POST',
                        body: formData
                    }});
                    const result = await response.json();
                    
                    if (result.needs_review) {{
                        showReviewForm(result);
                    }} else {{
                        addResult(result);
                    }}
                }} catch (error) {{
                    addResult({{
                        success: false,
                        original_name: file.name,
                        error: error.message
                    }});
                }}
            }}
            
            loading.classList.remove('visible');
            if (resultsList.children.length > 0) {{
                resultsCard.style.display = 'block';
            }}
        }}
        
        function addResult(result) {{
            const item = document.createElement('div');
            item.className = `result-item ${{result.success ? 'success' : 'error'}}`;
            
            let pathHtml = '';
            if (result.new_path) {{
                pathHtml = `<div class="result-path">📁 ${{result.new_path}}</div>`;
            }}
            
            item.innerHTML = `
                <span class="result-icon">${{result.success ? '✅' : '❌'}}</span>
                <div class="result-info">
                    <div class="result-original">${{result.original_name}}</div>
                    <div class="result-new">${{result.success ? result.new_name : result.error}}</div>
                    ${{pathHtml}}
                </div>
            `;
            
            resultsList.appendChild(item);
            resultsCard.style.display = 'block';
        }}
        
        function showReviewForm(result) {{
            reviewForm.classList.add('visible');
            document.getElementById('review-filename').value = result.original_name;
            document.getElementById('review-first').value = result.first_name || '';
            document.getElementById('review-last').value = result.last_name || '';
            document.getElementById('review-date').value = result.date_str || '';
        }}
        
        document.getElementById('review-submit').addEventListener('click', async () => {{
            const formData = new FormData();
            formData.append('filename', document.getElementById('review-filename').value);
            formData.append('first_name', document.getElementById('review-first').value);
            formData.append('last_name', document.getElementById('review-last').value);
            formData.append('date_str', document.getElementById('review-date').value);
            formData.append('format_type', selectedFormat);
            formData.append('output_folder', document.getElementById('output-folder').value);
            
            try {{
                const response = await fetch('/rename-manual', {{
                    method: 'POST',
                    body: formData
                }});
                const result = await response.json();
                addResult(result);
                reviewForm.classList.remove('visible');
            }} catch (error) {{
                addResult({{
                    success: false,
                    original_name: document.getElementById('review-filename').value,
                    error: error.message
                }});
            }}
        }});
        
        // Folder picker functionality
        const btnBrowse = document.getElementById('btn-browse');
        const folderInput = document.getElementById('output-folder');
        const folderName = document.getElementById('folder-name');
        const folderHint = document.getElementById('folder-hint');
        
        // Store the directory handle for later use
        let selectedDirHandle = null;
        
        // Check if File System Access API is available
        const hasFileSystemAccess = 'showDirectoryPicker' in window;
        
        if (!hasFileSystemAccess) {{
            // Fallback: show text input instead
            const folderDisplay = document.getElementById('folder-display');
            folderDisplay.innerHTML = `<input type="text" id="output-folder-text" value="${{folderInput.value}}" 
                style="flex:1; background:transparent; border:none; color:var(--text-primary); 
                font-family:'Space Mono',monospace; font-size:0.85rem;"
                placeholder="Enter folder path...">`;
            
            document.getElementById('output-folder-text').addEventListener('input', (e) => {{
                folderInput.value = e.target.value;
            }});
            
            btnBrowse.style.display = 'none';
            folderHint.textContent = 'Enter the full path to your output folder.';
        }}
        
        btnBrowse.addEventListener('click', async () => {{
            if (!hasFileSystemAccess) return;
            
            try {{
                // Request directory access
                selectedDirHandle = await window.showDirectoryPicker({{
                    id: 'jane-pdf-output',
                    mode: 'readwrite',
                    startIn: 'downloads'
                }});
                
                // Update display
                folderName.textContent = selectedDirHandle.name;
                folderName.classList.remove('placeholder');
                
                // Store the path (we'll need to resolve it on the server side)
                // For now, we'll use the handle's name and let the user know
                folderInput.value = selectedDirHandle.name;
                
                folderHint.innerHTML = `<span style="color: var(--accent-primary);">✓</span> Folder selected: <strong>${{selectedDirHandle.name}}</strong>`;
                
                // Store handle globally so we can write to it later
                window.selectedOutputDir = selectedDirHandle;
                
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    console.error('Error selecting folder:', err);
                    folderHint.textContent = 'Could not select folder. Please try again.';
                }}
            }}
        }});
        
        // Override the file handling to use the selected directory
        const originalHandleFiles = handleFiles;
        handleFiles = async function(files) {{
            // If we have a directory handle, we need to handle files differently
            if (window.selectedOutputDir) {{
                loading.classList.add('visible');
                resultsCard.style.display = 'none';
                resultsList.innerHTML = '';
                reviewForm.classList.remove('visible');
                
                for (const file of files) {{
                    if (!file.name.toLowerCase().endsWith('.pdf')) {{
                        addResult({{
                            success: false,
                            original_name: file.name,
                            error: 'Not a PDF file'
                        }});
                        continue;
                    }}
                    
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('format_type', selectedFormat);
                    formData.append('output_folder', '');  // Process without output folder first
                    
                    try {{
                        const response = await fetch('/upload', {{
                            method: 'POST',
                            body: formData
                        }});
                        const result = await response.json();
                        
                        if (result.needs_review) {{
                            showReviewForm(result);
                        }} else if (result.success) {{
                            // Now write the file to the selected directory
                            try {{
                                const tempResponse = await fetch(`/download/${{encodeURIComponent(result.new_name)}}`);
                                if (tempResponse.ok) {{
                                    const fileBlob = await tempResponse.blob();
                                    const fileHandle = await window.selectedOutputDir.getFileHandle(result.new_name, {{ create: true }});
                                    const writable = await fileHandle.createWritable();
                                    await writable.write(fileBlob);
                                    await writable.close();
                                    
                                    result.new_path = `${{window.selectedOutputDir.name}}/${{result.new_name}}`;
                                }}
                            }} catch (writeErr) {{
                                console.error('Error writing to selected folder:', writeErr);
                            }}
                            addResult(result);
                        }} else {{
                            addResult(result);
                        }}
                    }} catch (error) {{
                        addResult({{
                            success: false,
                            original_name: file.name,
                            error: error.message
                        }});
                    }}
                }}
                
                loading.classList.remove('visible');
                if (resultsList.children.length > 0) {{
                    resultsCard.style.display = 'block';
                }}
            }} else {{
                // Use original behavior with server-side path
                await originalHandleFiles(files);
            }}
        }};
    </script>
</body>
</html>
'''


def run_server(host: str = "127.0.0.1", port: int = 8080):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
