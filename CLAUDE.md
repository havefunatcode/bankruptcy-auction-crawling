# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

### Initial Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements_simple.txt  # Minimal dependencies
# pip install -r requirements.txt       # Full dependencies (includes pandas)

# Install Playwright browsers
playwright install

# Test installation
python main.py --preview
```

### Development Workflow
```bash
# Always activate virtual environment first
source venv/bin/activate

# Basic crawling (list data only)
python main.py --no-attachments --max-pages 1

# Enhanced crawling with attachments
python main.py --with-attachments --max-pages 2

# Debug mode (visible browser)
python main.py --headless false --max-pages 1

# Specific pages
python main.py --pages 1 5 10
```

## Architecture Overview

This is an asynchronous web crawler that scrapes Korean court bankruptcy auction notices from the Supreme Court website. The architecture follows a modular design with clear separation of concerns:

### Core Architecture Pattern
The system uses a **two-tier crawling approach**:
1. **Basic Mode**: Extracts only list-level data (pagination_handler.py)
2. **Enhanced Mode**: Navigates to detail pages and downloads attachments (enhanced_pagination_handler.py)

### Key Components

**Browser Management**
- `BrowserController`: Playwright session management with specialized navigation for the target site
- Handles complex navigation patterns including double-click fallback for detail page access
- Manages session state and form-based pagination

**Data Pipeline**
- `DataExtractor`: Parses HTML tables from list pages
- `DetailExtractor`: Extracts detailed information from individual notice pages  
- `AttachmentDownloader`: Handles JavaScript download functions and direct file downloads
- `DataStorage`: Outputs to CSV/JSON with comprehensive summaries

**Navigation Challenges**
The target website requires specialized handling:
- Detail page links sometimes need double-click instead of single click
- JavaScript-based pagination using hidden forms
- Session-dependent navigation that requires proper referrer handling
- Mixed attachment download methods (JavaScript functions vs direct links)

### File Organization
```
crawler/
├── browser_controller.py      # Playwright browser management
├── data_extractor.py         # HTML parsing for list pages
├── detail_extractor.py       # HTML parsing for detail pages
├── attachment_downloader.py   # File download handling
├── pagination_handler.py     # Basic list-only crawling
├── enhanced_pagination_handler.py  # Full crawling with attachments
└── data_storage.py           # Output generation
```

## Configuration

Key settings in `config.py`:
- `DELAY_BETWEEN_REQUESTS`: Rate limiting (default: 2.0 seconds)
- `DOWNLOAD_ATTACHMENTS`: Enable/disable attachment downloads
- `MAX_ATTACHMENT_SIZE_MB`: File size limits
- `ALLOWED_EXTENSIONS`: Permitted file types for download
- `HEADLESS`: Browser visibility for debugging

## Output Structure

**Data Files** (output/ directory):
- `bankruptcy_auctions_YYYYMMDD_HHMMSS.csv`: Main data export
- `bankruptcy_auctions_YYYYMMDD_HHMMSS_summary.txt`: Crawl statistics
- `attachment_summary_YYYYMMDD_HHMMSS.json`: Download metrics

**Attachments** (downloads/ directory):
```
downloads/
├── notice_405_공고제목/
│   ├── 01_첨부파일명.pdf
│   └── 02_다른파일.hwp
└── notice_404_다른공고/
    └── 01_공고문.pdf
```

## Site-Specific Implementation Details

### Navigation Patterns
The target site uses several non-standard navigation patterns:
- Form-based pagination with hidden pageIndex fields
- Detail pages that require double-click on some notices
- JavaScript download functions that trigger browser download dialogs

### Error Recovery
The crawler includes sophisticated error recovery for:
- Failed page navigation (automatic retry with different click methods)
- JavaScript download errors (fallback to direct link clicking)
- Session timeouts (automatic re-navigation to base URL)
- DOM state changes after page returns (fresh content extraction)

### Rate Limiting
Critical for this site - includes both time-based delays and respectful request patterns to avoid overloading the court website.

## Debugging

**Log Analysis**: Check `logs/` directory for detailed execution logs with debug-level information about navigation attempts and failures.

**Common Issues**:
- ModuleNotFoundError: Virtual environment not activated
- Navigation failures: Site structure may have changed, check selectors in browser_controller.py
- Download errors: JavaScript download functions may need updated handling in attachment_downloader.py

**Debug Mode**: Use `--headless false` to observe browser behavior during problematic operations.