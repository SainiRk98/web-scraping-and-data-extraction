# Data Extraction Project

A production-quality Python automation project that performs five data extraction tasks and stores results in Excel files.

---

## Project Structure

```
project/
├── config.py                  # Central configuration (URLs, paths, timeouts)
├── requirements.txt           # All Python dependencies
├── main.py                    # CLI entry point – run all or specific tasks
│
├── scrapers/
│   ├── property_scraper.py    # Task 1 – GrayPoint + Rightmove property data
│   ├── amazon_scraper.py      # Task 2 – Amazon India "Table Fan" products
│   └── instagram_scraper.py   # Task 3 – Instagram post comments & likes
│
├── extractors/
│   ├── pdf_extractor.py       # Task 4 – PDF table extraction (pages 13–24)
│   └── aadhaar_extractor.py   # Task 5 – Aadhaar card OCR
│
├── utils/
│   ├── logger.py              # Rotating file + console logger
│   ├── helper.py              # Retry decorator, WebDriver factory, HTTP helpers
│   └── excel_writer.py        # Styled Excel output (single & multi-sheet)
│
├── input/
│   ├── pdf/                   # Place your PDF here
│   └── aadhaar/               # Place Aadhaar card images here
│
└── output/                    # All Excel files are written here
    ├── property_data.xlsx
    ├── amazon_products.xlsx
    ├── instagram_post.xlsx
    ├── pdf_tables.xlsx
    └── aadhaar_data.xlsx
```

---

## Prerequisites

### 1. Python 3.11+
Download from https://www.python.org/downloads/

### 2. Google Chrome
Download from https://www.google.com/chrome/  
`webdriver-manager` will automatically download the matching ChromeDriver.

### 3. Tesseract OCR (for Task 5)
**Windows:**
```
Download installer: https://github.com/UB-Mannheim/tesseract/wiki
Default install path: C:\Program Files\Tesseract-OCR\tesseract.exe
```
**macOS:**
```bash
brew install tesseract
```
**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

### 4. Ghostscript (required by Camelot for Task 4)
**Windows:** https://www.ghostscript.com/releases/gsdnld.html  
**macOS:** `brew install ghostscript`  
**Linux:** `sudo apt-get install ghostscript`

---

## Installation

```bash
# 1. Navigate to the project directory
cd project

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install all dependencies
pip install -r requirements.txt
```

---

## Configuration

### Environment Variables

| Variable | Required For | Description |
|---|---|---|
| `INSTAGRAM_USERNAME` | Task 3 | Your Instagram login username or email |
| `INSTAGRAM_PASSWORD` | Task 3 | Your Instagram login password |
| `INSTAGRAM_POST_URL` | Task 3 | Full URL of the post to scrape |
| `AMAZON_MAX_PRODUCTS` | Task 2 | Number of products to scrape (default: 20) |
| `TESSERACT_CMD` | Task 5 | Path to tesseract.exe (Windows only if non-default) |
| `LOG_LEVEL` | All | DEBUG / INFO / WARNING / ERROR (default: INFO) |

**Windows – set environment variables:**
```cmd
set INSTAGRAM_USERNAME=your_username
set INSTAGRAM_PASSWORD=your_password
set INSTAGRAM_POST_URL=https://www.instagram.com/p/XXXXXXXXXX/
set AMAZON_MAX_PRODUCTS=30
```

**macOS / Linux:**
```bash
export INSTAGRAM_USERNAME=your_username
export INSTAGRAM_PASSWORD=your_password
export INSTAGRAM_POST_URL=https://www.instagram.com/p/XXXXXXXXXX/
```

Alternatively, create a `.env` file in the project root and load it with `python-dotenv`.

### config.py
All other settings (URLs, page ranges, timeouts, headless mode) are in `config.py`.  
Edit this file to change behaviour without touching scraper code.

---

## Usage

```bash
# Run all 5 tasks
python main.py

# Run specific tasks only
python main.py --tasks 4 5

# Task 2 with custom product count
python main.py --tasks 2 --max-products 50

# Task 3 with post URL passed directly
python main.py --tasks 3 --post-url https://www.instagram.com/p/XXXXXXXXXX/
```

---

## Task Details

### Task 1 – Property Scraper
- **Sources:** gray-point.com/properties/ and rightmove.co.uk/commercial-property-to-let.html
- **Method:** requests + BeautifulSoup for GrayPoint; Selenium for Rightmove (JS-rendered)
- **Pagination:** Automatic – scrapes all pages
- **Output:** `output/property_data.xlsx`

### Task 2 – Amazon Product Scraper
- **Source:** amazon.in – searches "Table Fan"
- **Method:** Selenium (handles JS, anti-bot measures)
- **Details:** Visits each product page individually for complete data
- **Output:** `output/amazon_products.xlsx`

### Task 3 – Instagram Scraper
- **Method:** Selenium with secure credential handling via environment variables
- **Note:** Instagram may require CAPTCHA solving on first login from a new IP
- **Output:** `output/instagram_post.xlsx`

### Task 4 – PDF Table Extractor
- **Input:** PDF in `input/pdf/`
- **Pages:** 13–24 (configurable in config.py)
- **Method:** Camelot (lattice → stream) with automatic pdfplumber fallback
- **Output:** `output/pdf_tables.xlsx` – one sheet per page

### Task 5 – Aadhaar OCR
- **Input:** Images in `input/aadhaar/` (jpg, jpeg, png, bmp, tiff)
- **Method:** Pillow pre-processing → Tesseract OCR → regex extraction
- **Output:** `output/aadhaar_data.xlsx`

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ChromeDriver` version mismatch | `pip install --upgrade webdriver-manager` |
| Tesseract not found | Set `TESSERACT_CMD` env variable to full path |
| Camelot import error | Install Ghostscript and `pip install camelot-py[cv]` |
| Amazon CAPTCHA | Run with `HEADLESS_BROWSER=False` in config.py and solve manually |
| Instagram login blocked | Use a fresh account; avoid running too frequently |
| Low OCR accuracy | Ensure images are high-resolution (300+ DPI); check lighting |

---

## Logs

All activity is logged to:
- **Console** – real-time output
- **project.log** – rotating file (5 MB × 3 backups)

Set `LOG_LEVEL=DEBUG` for verbose output.
