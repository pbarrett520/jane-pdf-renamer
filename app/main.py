"""
Jane PDF Renamer - Main Application Entry Point.

Usage:
    python -m app              # Opens the web GUI (browser-based)
    python -m app --cli <pdf>  # Headless rename
    python -m app --watch <folder>  # Watch folder mode
"""

import argparse
import logging
import sys
import webbrowser
from pathlib import Path

# Configure logging (HIPAA compliant - no PHI in logs)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_argparser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog='jane-pdf-renamer',
        description='Medical office PDF renaming tool for Jane app exports.'
    )
    
    parser.add_argument(
        '--cli',
        metavar='PDF_PATH',
        type=Path,
        help='Process a single PDF file in headless mode.'
    )
    
    parser.add_argument(
        '--watch',
        metavar='FOLDER',
        type=Path,
        help='Watch a folder for new PDFs and process them automatically.'
    )
    
    parser.add_argument(
        '--output',
        metavar='FOLDER',
        type=Path,
        help='Output folder for processed files (optional).'
    )
    
    parser.add_argument(
        '--format',
        choices=['current_discharge', 'appt_billing', 'appt_billing_eval', 
                 'appt_billing_progress', 'appt_billing_discharge'],
        default='appt_billing',
        help='Output filename format (default: appt_billing).'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port for web server (default: 8080).'
    )
    
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Don\'t automatically open browser.'
    )
    
    return parser


def run_cli(pdf_path: Path, output_folder: Path = None, format_type: str = 'appt_billing'):
    """Process a single PDF in CLI mode."""
    from core import PDFExtractor, PatientInfoParser, FileRenamer, FileFormat
    
    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        sys.exit(1)
    
    if not pdf_path.suffix.lower() == '.pdf':
        logger.error(f"Not a PDF file: {pdf_path}")
        sys.exit(1)
    
    try:
        file_format = FileFormat(format_type)
    except ValueError:
        file_format = FileFormat.APPT_BILLING
    
    # Extract and parse
    extractor = PDFExtractor()
    parser = PatientInfoParser()
    
    try:
        text = extractor.extract_text(pdf_path)
        # Pass filename for initials extraction
        info = parser.parse(text, filename=pdf_path.name)
        
        # Check confidence
        if info.confidence < 0.8 or not info.first_name or not info.last_name:
            print(f"⚠️  Needs review: {pdf_path.name}")
            print(f"   First: {info.first_name or '(unknown)'}, Last: {info.last_name or '(unknown)'}")
            print(f"   Confidence: {info.confidence:.0%}")
            sys.exit(1)
        
        # Rename the file
        renamer = FileRenamer(output_folder=output_folder, file_format=file_format)
        result_path = renamer.rename_file(pdf_path, info)
        
        print(f"✅ Renamed: {result_path.name}")
        print(f"   Path: {result_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def run_watch(folder: Path, output_folder: Path = None):
    """Watch a folder for new PDFs."""
    from app.watcher import FolderWatcher
    
    if not folder.exists():
        logger.error(f"Folder not found: {folder}")
        sys.exit(1)
    
    print(f"👁️  Watching folder: {folder}")
    if output_folder:
        print(f"📂 Output folder: {output_folder}")
    print("Press Ctrl+C to stop...")
    
    watcher = FolderWatcher(folder, output_folder)
    try:
        watcher.start()
    except KeyboardInterrupt:
        watcher.stop()
        print("\n✅ Stopped watching.")


def find_chromium_browser():
    """
    Find an installed Chromium-based browser.
    
    Returns the browser controller name or None if not found.
    Tries Chrome, Edge, and Brave in order.
    """
    import platform
    import subprocess
    
    system = platform.system()
    
    if system == "Darwin":  # macOS
        # Check for Chrome
        try:
            subprocess.run(
                ["osascript", "-e", 'id of application "Google Chrome"'],
                capture_output=True,
                check=True,
                timeout=2
            )
            return "chrome"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check for Edge
        try:
            subprocess.run(
                ["osascript", "-e", 'id of application "Microsoft Edge"'],
                capture_output=True,
                check=True,
                timeout=2
            )
            return "microsoft-edge"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Check for Brave
        try:
            subprocess.run(
                ["osascript", "-e", 'id of application "Brave Browser"'],
                capture_output=True,
                check=True,
                timeout=2
            )
            return "brave"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    elif system == "Windows":  # Windows
        # Check for Chrome in registry
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            winreg.CloseKey(key)
            return "chrome"
        except (ImportError, OSError):
            pass
        
        # Check for Edge
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe")
            winreg.CloseKey(key)
            return "microsoft-edge"
        except (ImportError, OSError):
            pass
        
        # Check for Brave
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe")
            winreg.CloseKey(key)
            return "brave"
        except (ImportError, OSError):
            pass
    
    return None


def open_in_chromium_browser(url: str):
    """
    Open URL in a Chromium-based browser if available, otherwise use default.
    
    Prioritizes Chrome/Edge/Brave because they support File System Access API.
    Falls back to default browser if no Chromium browser is found.
    """
    import platform
    import subprocess
    
    browser = find_chromium_browser()
    system = platform.system()
    
    if browser:
        try:
            if system == "Darwin":  # macOS
                if browser == "chrome":
                    subprocess.Popen(["open", "-a", "Google Chrome", url])
                elif browser == "microsoft-edge":
                    subprocess.Popen(["open", "-a", "Microsoft Edge", url])
                elif browser == "brave":
                    subprocess.Popen(["open", "-a", "Brave Browser", url])
                logger.info(f"Opened URL in {browser}")
                return True
            elif system == "Windows":
                if browser == "chrome":
                    subprocess.Popen(["start", "chrome", url], shell=True)
                elif browser == "microsoft-edge":
                    subprocess.Popen(["start", "msedge", url], shell=True)
                elif browser == "brave":
                    subprocess.Popen(["start", "brave", url], shell=True)
                logger.info(f"Opened URL in {browser}")
                return True
        except Exception as e:
            logger.warning(f"Could not open {browser}: {e}")
    
    # Fallback to default browser
    logger.info("No Chromium browser found, using default browser")
    webbrowser.open(url)
    return False


def run_gui(port: int = 8080, open_browser: bool = True):
    """Launch the web-based GUI."""
    import threading
    import time
    from app.web import run_server
    
    url = f"http://127.0.0.1:{port}"
    print(f"🌐 Starting web server at {url}")
    
    # Detect if Chromium browser is available
    chromium_detected = find_chromium_browser()
    if chromium_detected:
        print(f"✨ Opening in {chromium_detected.replace('-', ' ').title()} (supports folder picker)")
    else:
        print("⚠️  No Chromium browser detected - folder picker may not work")
        print("   Install Chrome, Edge, or Brave for full functionality")
    
    print("Press Ctrl+C to stop...")
    
    # Open browser after a short delay
    if open_browser:
        def open_browser_delayed():
            time.sleep(1.0)
            open_in_chromium_browser(url)
        threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    try:
        run_server(port=port)
    except KeyboardInterrupt:
        print("\n✅ Server stopped.")


def main():
    """Main entry point."""
    parser = setup_argparser()
    args = parser.parse_args()
    
    if args.cli:
        run_cli(args.cli, args.output, args.format)
    elif args.watch:
        run_watch(args.watch, args.output)
    else:
        run_gui(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
