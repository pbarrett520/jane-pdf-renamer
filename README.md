# Jane PDF Renamer

A cross-platform (macOS + Windows) local-only automation tool for medical office PDF workflow.

## 🏥 Purpose

Automatically rename patient chart PDFs downloaded from the Jane app using a standardized naming convention:

```
Last Name, First Name MM-DD-YYYY PT Note.pdf
```

## 🔒 HIPAA Compliance

This tool is designed with privacy as a first principle:

- ✅ **100% Local Processing** - No cloud, no external APIs
- ✅ **No PHI in Logs** - Only file paths, hashes, and status codes are logged
- ✅ **No Data Persistence** - Extracted text is never written to disk
- ✅ **Memory-Only Processing** - Patient information exists only during processing

## ⚡ Features

### Mode A: Drag & Drop (GUI)
1. Launch the application
2. Drag PDF(s) onto the window
3. Files are automatically renamed
4. If parsing confidence is low, a review form appears

### Mode B: Command Line
```bash
# Rename a single file
python -m app --cli path/to/chart.pdf

# Rename with output folder
python -m app --cli path/to/chart.pdf --output ./Processed

# Watch a folder for new PDFs
python -m app --watch ./Downloads --output ./Processed
```

## 📋 Naming Convention

**Input:** `HealthStre_Chart_1_TP_20251218_88209-2.pdf`  
**Output:** `Patient, Test 12-18-2025 PT Note.pdf`

- Always uses "PT Note" suffix (even if PDF says "Progress Note")
- Date format: MM-DD-YYYY
- Name format: Last Name, First Name
- Collision handling: Appends `_<hash>` if filename exists

## 🚀 Installation

### Prerequisites
- Python 3.10 or later

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd rename-file

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Application

#### Option 1: Web GUI Mode (Recommended for daily use)
```bash
# Launch the browser-based interface
python -m app

# Or specify a different port
python -m app --port 3000

# Start without auto-opening browser
python -m app --no-browser
```

This opens a browser at `http://127.0.0.1:8080` where you can:
- **Select output format** from 5 different naming conventions
- **Drag & drop** PDF files directly onto the page
- **Click to browse** and select files manually
- **Review and edit** patient info if parsing confidence is low
- **Set output folder** (optional)

#### Available Formats

| Format | Date Source | Output Filename |
|--------|-------------|-----------------|
| Current - Discharge | Today's date | `Last, First MMDDYY PT Chart Note.pdf` |
| Appt - Billing | Appointment date | `Last, First MMDDYY PT Note.pdf` |
| Appt - Billing (Eval) | Appointment date | `Last, First MMDDYY PT Eval Note.pdf` |
| Appt - Billing (Progress) | Appointment date | `Last, First MMDDYY PT Progress Note.pdf` |
| Appt - Billing (Discharge) | Appointment date | `Last, First MMDDYY PT Discharge Note.pdf` |

#### Option 2: CLI Mode (For scripting/automation)
```bash
# Rename a single file (default format: appt_billing)
python -m app --cli path/to/chart.pdf

# Specify format
python -m app --cli path/to/chart.pdf --format current_discharge

# Rename and move to output folder
python -m app --cli path/to/chart.pdf --output ./Processed
```

#### Option 3: Watch Mode (Automatic processing)
```bash
# Watch a folder and auto-process new PDFs
python -m app --watch ./Downloads --output ./Processed
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=core --cov=app
```

## 📦 Building Executables

### macOS

```bash
# Install PyInstaller
pip install pyinstaller

# Build the application
pyinstaller --name "Jane PDF Renamer" \
    --windowed \
    --onefile \
    --icon=assets/icon.icns \
    --add-data "config:config" \
    app/main.py

# The app will be in dist/
```

### Windows

```powershell
# Install PyInstaller
pip install pyinstaller

# Build the application
pyinstaller --name "Jane PDF Renamer" `
    --windowed `
    --onefile `
    --icon=assets/icon.ico `
    --add-data "config;config" `
    app/main.py

# The exe will be in dist/
```

### Cross-Platform Note
Build on the target platform - PyInstaller cannot cross-compile.

## ⚙️ Configuration

Edit `config/default.yaml` to customize behavior:

```yaml
# Output folder for processed PDFs
output_folder: null  # null = rename in place

# Create a "Processed" subfolder
create_processed_subfolder: false

# Naming settings
naming:
  date_format: "MM-DD-YYYY"
  suffix: "PT Note"
```

## 🔧 Project Structure

```
rename-file/
├── app/                    # Application code
│   ├── __init__.py
│   ├── __main__.py        # Entry point
│   ├── main.py            # CLI/GUI launcher
│   ├── gui.py             # PySide6 GUI
│   └── watcher.py         # Folder watcher
├── core/                   # Core business logic
│   ├── __init__.py
│   ├── extractor.py       # PDF text extraction
│   ├── parser.py          # Patient info parsing
│   └── renamer.py         # File renaming
├── tests/                  # Test suite
│   └── test_pdf_processing.py
├── config/
│   └── default.yaml       # Configuration
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 📖 Parsing Rules

The parser looks for specific patterns in Jane PDF exports:

1. **Patient Name:**
   - Find line containing just "Chart"
   - Next non-empty line is patient display name
   - Strip trailing number (e.g., "Test Patient 1" → "Test Patient")
   - Last word = Last Name, rest = First Name

2. **Appointment Date:**
   - Find pattern: `MonthName DD, YYYY` (e.g., "December 18, 2025")
   - Convert to MM-DD-YYYY format

## 🐛 Troubleshooting

### "Needs Review" Dialog Appears
- The parser couldn't confidently extract all information
- Manually enter/correct the patient name and date
- Click "Rename" to proceed

### File Not Processing
- Ensure the file is a valid PDF
- Check that it follows the expected Jane export format
- Try the CLI with verbose logging for more details

### Empty Text Extraction
- The PDF may be image-based (scanned)
- OCR support is planned for a future version

## 📄 License

This software is provided for internal use at medical offices. 
All patient data remains local and is never transmitted.

## 🤝 Contributing

1. Run tests before submitting changes
2. Ensure no PHI is logged or stored
3. Follow existing code style

