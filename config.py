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

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FILE = "crawler.log"