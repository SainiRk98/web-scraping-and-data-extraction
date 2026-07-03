"""
extractors/pdf_extractor.py
----------------------------
Task 4 – Extract tables from pages 13–24 of a PDF file.

Strategy:
  1. Try Camelot first (best for bordered/lattice tables).
  2. If Camelot fails or returns no tables, fall back to pdfplumber.

Each PDF page becomes a separate Excel sheet named "Page_<N>".
Table structure is preserved exactly.

Input:  Any PDF placed in input/pdf/
Output: pdf_tables.xlsx  (one sheet per page)
"""

import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import pdfplumber

from config import PDF_DIR, PDF_START_PAGE, PDF_END_PAGE, PDF_EXCEL, NOT_AVAILABLE
from utils.excel_writer import write_multiple_sheets
from utils.logger import get_logger

log = get_logger(__name__)

# Try importing camelot; mark as unavailable if not installed
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    log.warning("camelot-py not installed – will use pdfplumber only.")


# ── Camelot Extraction ────────────────────────────────────────────────────────

def _extract_with_camelot(pdf_path: str, page_num: int) -> Optional[pd.DataFrame]:
    """
    Attempt to extract tables from a single page using Camelot.
    Tries 'lattice' first, then 'stream' flavour.
    Returns a combined DataFrame or None on failure.
    """
    if not CAMELOT_AVAILABLE:
        return None

    for flavor in ("lattice", "stream"):
        try:
            tables = camelot.read_pdf(
                pdf_path,
                pages=str(page_num),
                flavor=flavor,
                suppress_stdout=True,
            )
            if tables and len(tables) > 0:
                frames = [t.df for t in tables if not t.df.empty]
                if frames:
                    combined = pd.concat(frames, ignore_index=True)
                    log.debug("Camelot (%s) extracted %d table(s) from page %d.", flavor, len(frames), page_num)
                    return combined
        except Exception as exc:
            log.debug("Camelot %s failed on page %d: %s", flavor, page_num, exc)

    return None


# ── pdfplumber Extraction ─────────────────────────────────────────────────────

def _extract_with_pdfplumber(pdf_path: str, page_num: int) -> Optional[pd.DataFrame]:
    """
    Extract tables from a single page using pdfplumber.
    Returns a combined DataFrame or None if no tables found.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # pdfplumber uses 0-based page index
            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()

            if not tables:
                # Fall back to extracting raw text as a single-column table
                text = page.extract_text()
                if text:
                    rows = [[line] for line in text.splitlines() if line.strip()]
                    df = pd.DataFrame(rows, columns=["Content"])
                    log.debug("pdfplumber: extracted text (no tables) from page %d.", page_num)
                    return df
                return None

            frames = []
            for table in tables:
                if not table:
                    continue
                # Use first row as header if it looks like a header
                df = pd.DataFrame(table)
                if df.empty:
                    continue
                # Promote first row to header
                df.columns = df.iloc[0].fillna("").astype(str)
                df = df[1:].reset_index(drop=True)
                # Replace None with NOT_AVAILABLE
                df = df.fillna(NOT_AVAILABLE)
                frames.append(df)

            if frames:
                combined = pd.concat(frames, ignore_index=True)
                log.debug("pdfplumber extracted %d table(s) from page %d.", len(frames), page_num)
                return combined

    except Exception as exc:
        log.error("pdfplumber failed on page %d: %s", page_num, exc)

    return None


# ── Per-Page Orchestrator ─────────────────────────────────────────────────────

def _extract_page(pdf_path: str, page_num: int) -> pd.DataFrame:
    """
    Extract tables from one page using Camelot → pdfplumber fallback.
    Always returns a DataFrame (may contain a 'Note' column if nothing found).
    """
    log.info("Extracting page %d ...", page_num)

    # Try Camelot
    df = _extract_with_camelot(pdf_path, page_num)
    if df is not None and not df.empty:
        log.info("Page %d: Camelot succeeded (%d rows).", page_num, len(df))
        return df

    # Fall back to pdfplumber
    log.info("Page %d: Camelot returned nothing – trying pdfplumber.", page_num)
    df = _extract_with_pdfplumber(pdf_path, page_num)
    if df is not None and not df.empty:
        log.info("Page %d: pdfplumber succeeded (%d rows).", page_num, len(df))
        return df

    log.warning("Page %d: No tables or text found.", page_num)
    return pd.DataFrame([{"Note": f"No tables found on page {page_num}"}])


# ── Public Entry Point ────────────────────────────────────────────────────────

def run() -> None:
    """
    Find the first PDF in input/pdf/, extract pages PDF_START_PAGE–PDF_END_PAGE,
    and write each page to a separate Excel sheet.
    """
    log.info("=== Task 4: PDF Table Extractor ===")

    # Locate PDF file
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        log.error("No PDF files found in %s", PDF_DIR)
        write_multiple_sheets(
            {"Error": pd.DataFrame([{"Note": f"No PDF found in {PDF_DIR}"}])},
            PDF_EXCEL,
        )
        return

    pdf_path = str(pdf_files[0])
    log.info("Processing PDF: %s", pdf_path)

    # Determine actual page count
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception as exc:
        log.error("Cannot open PDF: %s", exc)
        return

    start = max(1, PDF_START_PAGE)
    end   = min(total_pages, PDF_END_PAGE)
    log.info("PDF has %d pages. Extracting pages %d–%d.", total_pages, start, end)

    sheets: Dict[str, pd.DataFrame] = {}
    for page_num in range(start, end + 1):
        sheet_name = f"Page_{page_num}"
        df = _extract_page(pdf_path, page_num)
        sheets[sheet_name] = df

    write_multiple_sheets(sheets, PDF_EXCEL)
    log.info("Task 4 complete → %s (%d sheets)", PDF_EXCEL.name, len(sheets))
