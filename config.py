"""
config.py
---------
Central configuration for the entire project.
All paths, URLs, timeouts, and toggles are defined here.
Import this module in any other file to access settings.
"""

import os
from pathlib import Path

# ── Base Paths ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
INPUT_DIR   = BASE_DIR / "input"
OUTPUT_DIR  = BASE_DIR / "output"
PDF_DIR     = INPUT_DIR / "pdf"
AADHAAR_DIR = INPUT_DIR / "aadhaar"

# Ensure output directory exists at import time
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Output Excel Files ────────────────────────────────────────────────────────
PROPERTY_EXCEL  = OUTPUT_DIR / "property_data.xlsx"
AMAZON_EXCEL    = OUTPUT_DIR / "amazon_products.xlsx"
INSTAGRAM_EXCEL = OUTPUT_DIR / "instagram_post.xlsx"
PDF_EXCEL       = OUTPUT_DIR / "pdf_tables.xlsx"
AADHAAR_EXCEL   = OUTPUT_DIR / "aadhaar_data.xlsx"

# ── Task 1 – Property Scraper ─────────────────────────────────────────────────
GRAYPOINT_URL  = "https://www.gray-point.com/properties/"
RIGHTMOVE_URL  = "https://www.rightmove.co.uk/commercial-property-to-let.html"

# ── Task 2 – Amazon Scraper ───────────────────────────────────────────────────
AMAZON_BASE_URL   = "https://www.amazon.in"
AMAZON_SEARCH_KW  = "Table Fan"
AMAZON_MAX_PRODUCTS = int(os.getenv("AMAZON_MAX_PRODUCTS", "20"))  # configurable

# ── Task 3 – Instagram ────────────────────────────────────────────────────────
# Credentials are read from environment variables – never hardcoded.
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
# Set this env-var to the post URL you want to scrape, e.g.:
#   set INSTAGRAM_POST_URL=https://www.instagram.com/p/XXXXXXXXXXX/
INSTAGRAM_POST_URL = os.getenv("INSTAGRAM_POST_URL", "")

# ── Task 4 – PDF Extraction ───────────────────────────────────────────────────
PDF_START_PAGE = 13   # 1-based page numbers
PDF_END_PAGE   = 24

# ── Task 5 – Aadhaar OCR ─────────────────────────────────────────────────────
# Path to Tesseract executable (Windows default; override via env-var)
TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# ── Selenium / Browser ────────────────────────────────────────────────────────
HEADLESS_BROWSER  = True          # Set False to watch the browser
PAGE_LOAD_TIMEOUT = 30            # seconds
IMPLICIT_WAIT     = 10            # seconds
EXPLICIT_WAIT     = 20            # seconds
MAX_RETRIES       = 3             # retry attempts for network calls

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")   # DEBUG | INFO | WARNING | ERROR
LOG_FILE  = BASE_DIR / "project.log"

# ── Placeholder for missing data ──────────────────────────────────────────────
NOT_AVAILABLE = "Not Available"
