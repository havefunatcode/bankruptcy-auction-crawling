"""
Configuration settings for bankruptcy auction crawler
"""

# URL Configuration
BASE_URL = "https://www.scourt.go.kr/portal/notice/realestate/RealNoticeList.work"

# Crawling Configuration
DELAY_BETWEEN_REQUESTS = 2.0  # seconds
PAGE_LOAD_TIMEOUT = 30000  # milliseconds
MAX_RETRIES = 3
RETRY_DELAY = 5.0  # seconds

# Browser Configuration
HEADLESS = True
BROWSER_TYPE = "chromium"  # chromium, firefox, webkit

# Output Configuration
OUTPUT_DIR = "output"
OUTPUT_FORMAT = "csv"  # csv, json, both
OUTPUT_FILENAME = "bankruptcy_auctions"

# Attachment Download Configuration
DOWNLOAD_ATTACHMENTS = True
DOWNLOADS_DIR = "downloads"
MAX_ATTACHMENT_SIZE_MB = 100  # Maximum file size to download
ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.hwp', '.zip', '.xlsx', '.xls', '.txt']

# PDF Processing Configuration (opendataloader-pdf 기반)
PROCESS_PDFS = True  # 다운로드 직후 PDF 처리 활성화
PDF_PROCESSING_ENABLED = True  # PDF 컨텐츠 DB 저장 활성화
PDF_OUTPUT_DIR = "parsed_pdfs"  # opendataloader-pdf JSON 출력 디렉토리
PDF_IMAGE_OUTPUT = "off"  # "off" | "external" | "embedded"
PDF_IMAGE_DIR = "extracted_images"

# Hybrid (AI) 모드 — 어려운 PDF(스캔/borderless 테이블)용
# 사용 전 별도 데몬 실행: opendataloader-pdf-hybrid --port 5002
PDF_HYBRID_MODE = None  # None | "docling-fast" | "hancom-ai"
PDF_HYBRID_URL = None  # 원격 서버 사용 시 "http://host:5002"
PDF_HYBRID_FALLBACK = False  # 하이브리드 실패 시 로컬 모드로 폴백

# Database Configuration (MySQL 8.0+)
DB_ENABLED = True
DB_HOST = "localhost"
DB_PORT = 3306
DB_NAME = "bankruptcy_auction"
DB_USER = "root"
DB_PASSWORD = ""
DB_CHARSET = "utf8mb4"

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FILE = "crawler.log"