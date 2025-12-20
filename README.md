# Jane PDF Renamer

A cross-platform (macOS + Windows) local-only automation tool for medical office PDF workflow.

## 🏥 Purpose

Automatically rename patient chart PDFs downloaded from the Jane app using standardized naming conventions. Choose from 5 different formats based on your workflow needs.

**Example:**
- **Input:** `HealthStre_Chart_1_TP_20251218_88209-2.pdf`
- **Output:** `Patient, Test 121825 PT Note.pdf`

## 🔒 HIPAA Compliance

This tool is designed with privacy as a first principle:

- ✅ **100% Local Processing** - No cloud, no external APIs
- ✅ **No PHI in Logs** - Only file paths, hashes, and status codes are logged
- ✅ **No Data Persistence** - Extracted text is never written to disk
- ✅ **Memory-Only Processing** - Patient information exists only during processing

## ⚡ Features

- **Web-based GUI** - Modern browser interface with drag-and-drop
- **5 Naming Formats** - Choose date source (today vs appointment) and suffix
- **Native Folder Picker** - Click to select output directory
- **CLI Mode** - For scripting and automation
- **Watch Mode** - Auto-process new PDFs in a folder
- **Collision Prevention** - Appends hash if filename exists

## 📋 Naming Formats

| Format | Date Source | Output Filename |
|--------|-------------|-----------------|
| Current - Discharge | Today's date | `Last, First MMDDYY PT Chart Note.pdf` |
| Appt - Billing | Appointment date | `Last, First MMDDYY PT Note.pdf` |
| Appt - Billing (Eval) | Appointment date | `Last, First MMDDYY PT Eval Note.pdf` |
| Appt - Billing (Progress) | Appointment date | `Last, First MMDDYY PT Progress Note.pdf` |
| Appt - Billing (Discharge) | Appointment date | `Last, First MMDDYY PT Discharge Note.pdf` |

- **Date format:** MMDDYY (e.g., 121825 for December 18, 2025)
- **Name format:** Last, First

## 🚀 Installation

### Prerequisites
- Python 3.10 or later

### Setup

```bash
# Clone the repository
git clone https://github.com/pbarrett520/jane-pdf-renamer.git
cd jane-pdf-renamer

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 🖥️ Usage

### Option 1: Web GUI (Recommended)

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
- **Browse for output folder** using native folder picker

### Option 2: CLI Mode

```bash
# Rename a single file (default format: appt_billing)
python -m app --cli path/to/chart.pdf

# Specify format
python -m app --cli path/to/chart.pdf --format current_discharge
python -m app --cli path/to/chart.pdf --format appt_billing_eval

# Rename and move to output folder
python -m app --cli path/to/chart.pdf --output ./Processed
```

### Option 3: Watch Mode

```bash
# Watch a folder and auto-process new PDFs
python -m app --watch ./Downloads --output ./Processed
```

## 🧪 Testing

```bash
# Run all tests (28 tests)
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=core --cov=app
```

## 🔧 Project Structure

```
jane-pdf-renamer/
├── app/                        # Application code
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── main.py                # CLI/GUI launcher
│   ├── web.py                 # FastAPI server
│   ├── watcher.py             # Folder watcher
│   ├── templates/             # Jinja2 HTML templates
│   │   └── index.html
│   └── static/                # Static assets
│       ├── css/
│       │   └── styles.css
│       └── js/
│           └── app.js
├── core/                       # Core business logic
│   ├── __init__.py
│   ├── extractor.py           # PDF text extraction (pdfplumber)
│   ├── parser.py              # Patient info parsing
│   └── renamer.py             # File renaming with format support
├── tests/                      # Test suite (28 tests)
│   └── test_pdf_processing.py
├── config/
│   └── default.yaml           # Configuration
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 📖 Parsing Rules

The parser extracts information from Jane PDF exports:

1. **Patient Name:**
   - Find line containing "Chart"
   - Next non-empty line is patient display name
   - Strip trailing number (e.g., "Test Patient 1" → "Test Patient")
   - **Smart Name Splitting:** Uses initials from filename to correctly split compound names
     - Filename `..._AN_...pdf` + "Anna Nogales Ramirez" → First: "Anna", Last: "Nogales Ramirez"
     - Filename `..._TN_...pdf` + "Tony Chan Nguyen" → First: "Tony Chan", Last: "Nguyen"
   - Falls back to "last word = last name" if no initials found

2. **Appointment Date:**
   - Find pattern: `MonthName DD, YYYY` (e.g., "December 18, 2025")
   - Convert to MMDDYY format (e.g., "121825")

## 📦 Building Executables

### macOS

```bash
pip install pyinstaller

pyinstaller --name "Jane PDF Renamer" \
    --onefile \
    --add-data "app/templates:app/templates" \
    --add-data "app/static:app/static" \
    --add-data "config:config" \
    app/main.py
```

### Windows

```powershell
pip install pyinstaller

pyinstaller --name "Jane PDF Renamer" `
    --onefile `
    --add-data "app/templates;app/templates" `
    --add-data "app/static;app/static" `
    --add-data "config;config" `
    app/main.py
```

## 🐛 Troubleshooting

### "Needs Review" Dialog Appears
- The parser couldn't confidently extract all information
- Manually enter/correct the patient name and date
- Click "Rename" to proceed

### File Not Processing
- Ensure the file is a valid PDF
- Check that it follows the expected Jane export format
- Try the CLI for more details

### Folder Picker Not Working
- The File System Access API requires Chrome, Edge, or another Chromium browser
- Firefox/Safari users can manually enter the output path

## 📄 License

This software is provided for internal use at medical offices. 
All patient data remains local and is never transmitted.

## 🤝 Contributing

1. Run tests before submitting changes: `pytest tests/ -v`
2. Ensure no PHI is logged or stored
3. Follow existing code style
