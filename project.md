# Project Development Log

## Jane PDF Renamer - Development Session Summary

This document chronicles the development of the Jane PDF Renamer application from initial concept to completion.

---

## 🎯 Project Goal

Build a cross-platform (macOS + Windows) local-only automation tool for a medical office workflow that:
- Renames PDF chart exports from the Jane app
- Maintains strict HIPAA compliance (no PHI in logs, no cloud processing)
- Supports multiple naming format options
- Provides both GUI and CLI interfaces

---

## 📅 Development Timeline

### Phase 1: Foundation & Core Logic (TDD Approach)

**Objective:** Establish core PDF processing with test-driven development.

1. **Examined Sample PDF** - Analyzed `HealthStre_Chart_1_TP_20251218_88209-2.pdf` to understand:
   - Document structure ("Chart" keyword followed by patient name)
   - Date format (MonthName DD, YYYY)
   - Expected parsing rules

2. **Created Test Suite** - Wrote 27 comprehensive tests covering:
   - PDF text extraction
   - Patient name parsing (including trailing numbers, multi-word names)
   - Date extraction and formatting
   - File renaming with collision prevention
   - HIPAA compliance (no PHI in logs)

3. **Implemented Core Modules:**
   - `core/extractor.py` - PDF text extraction using pdfplumber
   - `core/parser.py` - Patient info parsing with confidence scoring
   - `core/renamer.py` - File renaming with hash-based collision prevention

4. **Initial Output Format:**
   ```
   Last Name, First Name MM-DD-YYYY PT Note.pdf
   ```

---

### Phase 2: Native GUI (PySide6)

**Objective:** Create a cross-platform native desktop GUI.

- Built drag-and-drop interface using PySide6 (Qt for Python)
- Implemented file processing workflow
- Added manual review form for low-confidence parsing

**Outcome:** Working but limited to native desktop experience.

---

### Phase 3: Web-Based GUI (FastAPI)

**Objective:** Replace native GUI with browser-based interface for better Playwright testing and modern UX.

1. **Replaced PySide6 with FastAPI** - Full web-based architecture
2. **Added 5 Naming Formats** per user requirements:

   | Format | Date Source | Suffix |
   |--------|-------------|--------|
   | Current - Discharge | Today's date | PT Chart Note |
   | Appt - Billing | Appointment date | PT Note |
   | Appt - Billing (Eval) | Appointment date | PT Eval Note |
   | Appt - Billing (Progress) | Appointment date | PT Progress Note |
   | Appt - Billing (Discharge) | Appointment date | PT Discharge Note |

3. **Updated Date Format** - Changed from `MM-DD-YYYY` to `MMDDYY`
   - Old: `Patient, Test 12-18-2025 PT Note.pdf`
   - New: `Patient, Test 121825 PT Note.pdf`

4. **Implemented Radio Button Selection** - Clean format picker in GUI

5. **Updated Test Suite** - All 28 tests updated for new format, all passing

---

### Phase 4: Folder Picker Enhancement

**Objective:** Replace manual path entry with native folder selection.

1. **Added File System Access API** - Modern browser directory picker
2. **Implemented fallback** - Text input for unsupported browsers (Firefox, Safari)
3. **Updated UI** - "Browse" button with folder display

---

### Phase 5: Code Refactoring

**Objective:** Separate concerns for maintainability.

**Before:** `web.py` was 1,155 lines with embedded HTML/CSS/JS as a string.

**After:** Clean separation into:
```
app/
├── web.py              # FastAPI server (~250 lines)
├── templates/
│   └── index.html      # Jinja2 template
└── static/
    ├── css/
    │   └── styles.css  # All CSS (~350 lines)
    └── js/
        └── app.js      # All JavaScript (~250 lines)
```

---

### Phase 6: Git Repository Setup

**Objective:** Version control and GitHub hosting.

1. Initialized git repository
2. Created comprehensive `.gitignore`
3. Excluded sample PDF (test data with PHI)
4. Pushed to GitHub: `https://github.com/pbarrett520/jane-pdf-renamer`

**Commits:**
1. Initial commit with full application
2. Remove unused PySide6 native GUI code
3. Refactor: Separate HTML, CSS, and JS into dedicated files

---

### Phase 7: Multi-Word Surname Parsing Fix

**Objective:** Correctly handle Latino/compound surnames (e.g., "Anna Nogales Ramirez") and multi-word first names (e.g., "Tony Chan Nguyen").

**Problem Identified:**
The original parser assumed the last word was always the last name:
```python
# Old approach - INCORRECT for compound names
parts = name.split()
last_name = parts[-1]      # "Ramirez" 
first_name = ' '.join(parts[:-1])  # "Anna Nogales" ← WRONG!
```

For "Anna Nogales Ramirez" this produced:
- First: "Anna Nogales", Last: "Ramirez" ❌

But Harriet needed:
- First: "Anna", Last: "Nogales Ramirez" ✓

**Solution: Use Filename Initials**

Jane PDF filenames include patient initials (e.g., `HealthStre_Chart_1_AN_20251218.pdf` for "Anna Nogales Ramirez"):
- First letter = first name initial
- Second letter = last name initial

**New Algorithm:**
```python
# Try each split point until initials match
for split_idx in range(1, len(parts)):
    potential_first = ' '.join(parts[:split_idx])
    potential_last = ' '.join(parts[split_idx:])
    
    if (potential_first[0] == first_initial and 
        potential_last[0] == last_initial):
        return potential_first, potential_last  # ✓ MATCH
```

**Examples:**
| Full Name | Initials | First Name | Last Name |
|-----------|----------|------------|-----------|
| Anna Nogales Ramirez | AN | Anna | Nogales Ramirez |
| Tony Chan Nguyen | TN | Tony Chan | Nguyen |
| Test Patient | TP | Test | Patient |

**Files Updated:**
- `core/parser.py` - Added `extract_initials_from_filename()` function and initials-based splitting logic
- `app/web.py` - Passes original filename to parser for initials extraction
- `app/main.py` - Passes filename to parser in CLI mode
- `app/watcher.py` - Passes filename to parser in watch mode

---

### Phase 8: Batch Processing UX Enhancements

**Objective:** Make batch processing capability more visible and user-friendly.

**Discovery:**
The application already supported batch processing since Phase 3:
- HTML file input had `multiple` attribute
- JavaScript looped through all dropped/selected files
- Results displayed sequentially

**Problem:**
Users didn't realize they could process multiple files because the UI didn't clearly indicate this capability.

**Solution:**
Enhanced the UI to make batch processing obvious:

1. **Updated Drop Zone Text:**
   - Before: "Drop PDF files here"
   - After: "Drop one or more PDF files here" + "supports batch processing"

2. **Added Progress Tracking:**
   ```javascript
   if (totalFiles > 1) {
       loadingText.textContent = `Processing ${totalFiles} PDFs...`;
       loadingProgress.textContent = `File ${processedCount} of ${totalFiles}`;
   }
   ```

3. **Visual Feedback:**
   - Shows "Processing 5 PDFs..." when multiple files are uploaded
   - Live progress: "File 3 of 5"
   - All results displayed in a scrollable list

**User Experience:**
- Harriet can now select/drag 10+ PDFs at once
- Clear feedback on processing progress
- Sequential processing prevents overwhelming the system
- All results visible at the end for review

---

## 🏗️ Final Architecture

```
jane-pdf-renamer/
├── app/                        # Application layer
│   ├── main.py                # Entry point (CLI args, server launch)
│   ├── web.py                 # FastAPI routes and API endpoints
│   ├── watcher.py             # Folder watching for auto-processing
│   ├── templates/index.html   # Main page template
│   └── static/                # Frontend assets
│       ├── css/styles.css
│       └── js/app.js
├── core/                       # Business logic layer
│   ├── extractor.py           # PDF → text
│   ├── parser.py              # text → PatientInfo
│   └── renamer.py             # PatientInfo → renamed file
├── tests/                      # 28 comprehensive tests
├── config/                     # YAML configuration
└── requirements.txt           # Dependencies
```

---

## 🔧 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| PDF Extraction | pdfplumber | Reliable text extraction |
| Web Framework | FastAPI | Modern async Python web server |
| Templating | Jinja2 | HTML template rendering |
| Frontend | Vanilla JS + CSS | No framework dependencies |
| Testing | pytest | Test-driven development |
| Packaging | PyInstaller | Cross-platform executables |

---

## ✅ Test Coverage

**28 tests covering:**

- **PDFExtractor (6 tests)**
  - Text extraction, keyword detection, error handling, HIPAA compliance

- **PatientInfoParser (11 tests)**
  - Name extraction, date parsing, confidence scoring, edge cases

- **FileRenamer (7 tests)**
  - Filename generation, format options, collision handling

- **End-to-End (2 tests)**
  - Full pipeline validation

- **HIPAA Compliance (2 tests)**
  - No PHI in logs, no text caching

---

## 🔐 Security Considerations

1. **No External Network Calls** - All processing is local
2. **No PHI Logging** - Only file hashes and paths logged
3. **No Text Persistence** - Extracted content only in memory
4. **No Cloud Dependencies** - Works fully offline

---

## 🚀 Deployment Options

1. **Development:** `python -m app`
2. **Production:** PyInstaller executable
3. **Server:** Deploy FastAPI behind nginx/reverse proxy

---

## 📝 Lessons Learned

1. **TDD Works** - Writing tests first caught edge cases early
2. **Web > Native for Testing** - Playwright can interact with browser UI
3. **Separation of Concerns** - Embedded HTML is unmaintainable
4. **File System Access API** - Modern browsers have powerful local file APIs
5. **Use All Available Data** - Filename metadata (initials) solved name parsing ambiguity

---

## 🔮 Future Enhancements

- [ ] OCR support for scanned PDFs
- [ ] Batch processing progress bar
- [ ] Custom format string configuration
- [ ] Export processing history
- [ ] Dark/light theme toggle

