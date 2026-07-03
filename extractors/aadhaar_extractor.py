"""
extractors/aadhaar_extractor.py
--------------------------------
Task 5 - Extract personal information from Aadhaar card images using OCR.

Extracted fields:
  Name, Date of Birth, Gender, Aadhaar Number,
  Address, City, State, Pin Code

Pipeline:
  1. Pre-process image (grayscale, denoise, threshold) with Pillow
  2. Run Tesseract OCR via pytesseract
  3. Apply regex patterns to extract each field
  4. Write "Not Available" for any field that cannot be extracted

Input:  Images in input/aadhaar/  (jpg, jpeg, png, bmp, tiff)
Output: aadhaar_data.xlsx
"""

import re
from pathlib import Path
from typing import Dict, List

import pytesseract
from PIL import Image, ImageFilter, ImageEnhance

from config import AADHAAR_DIR, AADHAAR_EXCEL, NOT_AVAILABLE, TESSERACT_CMD
from utils.excel_writer import records_to_excel
from utils.logger import get_logger

log = get_logger(__name__)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# Tokens that are never part of a person's name on an Aadhaar card
_NON_NAME_TOKENS = {
    "government", "india", "unique", "identification", "authority",
    "uidai", "aadhaar", "enrollment", "enrolment", "address",
    "male", "female", "dob", "year", "birth", "valid", "help",
    "www", "http", "uid", "vid", "download", "digitally", "signed",
    "republic", "department", "ministry", "income", "tax",
}


# ── Image Pre-processing ──────────────────────────────────────────────────────

def _preprocess_image(image_path: Path) -> Image.Image:
    """Enhance image for better OCR: upscale, grayscale, contrast, sharpen, binarise."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if w < 1000:
        scale = 1000 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda p: 255 if p > 140 else 0)
    return img


# ── OCR ───────────────────────────────────────────────────────────────────────

def _run_ocr(image_path: Path) -> str:
    """Run Tesseract OCR and return raw text."""
    try:
        img = _preprocess_image(image_path)
        config = "--psm 6 --oem 3 -l eng"
        text = pytesseract.image_to_string(img, config=config)
        log.debug("OCR raw for %s:\n%s", image_path.name, text[:400])
        return text
    except Exception as exc:
        log.error("OCR failed for %s: %s", image_path.name, exc)
        return ""


# ── Field Extractors ──────────────────────────────────────────────────────────

def _clean_name(raw: str) -> str:
    """
    Validate a name candidate:
    - Take only the first line
    - Strip non-alpha chars
    - Must be 2-5 words, each 2+ chars, no blacklisted tokens
    """
    first_line = raw.split("\n")[0].strip()
    cleaned = re.sub(r"[^A-Za-z\s]", "", first_line).strip()
    words = cleaned.split()
    if 2 <= len(words) <= 5:
        if not any(w.lower() in _NON_NAME_TOKENS for w in words):
            if all(len(w) >= 2 for w in words):
                return " ".join(w.capitalize() for w in words)
    return ""


def _extract_name(text: str) -> str:
    """
    Try multiple patterns to find the cardholder name.
    Aadhaar cards print name after 'Government of India' header
    or labelled with 'Name:'.
    """
    patterns = [
        # Explicit label
        r"(?:^|\n)\s*(?:Name|naam)\s*[:\-]\s*([A-Za-z][A-Za-z\s]{2,40})",
        # Line after Government of India header
        r"(?:Government of India|GOVERNMENT OF INDIA)\s*\n+\s*([A-Z][a-zA-Z\s]{3,40})",
        # Title-case standalone line (2-5 words)
        r"^([A-Z][a-z]{1,20}(?:\s[A-Z][a-z]{1,20}){1,4})$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE | re.IGNORECASE)
        if m:
            candidate = _clean_name(m.group(1))
            if candidate:
                return candidate
    return NOT_AVAILABLE


def _extract_dob(text: str) -> str:
    """Extract Date of Birth (DD/MM/YYYY or DD-MM-YYYY)."""
    patterns = [
        r"(?:DOB|Date\s*of\s*Birth|DOB\s*:)[:\s]+(\d{2}[\/\-]\d{2}[\/\-]\d{4})",
        r"\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b",
        r"(?:Year\s*of\s*Birth|YOB)[:\s]+(\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return NOT_AVAILABLE


def _extract_gender(text: str) -> str:
    """Extract gender."""
    m = re.search(r"\b(Male|Female|Transgender|MALE|FEMALE)\b", text)
    if m:
        return m.group(1).strip().capitalize()
    return NOT_AVAILABLE


def _extract_aadhaar_number(text: str) -> str:
    """
    Extract 12-digit Aadhaar number.
    Handles: spaced (XXXX XXXX XXXX), masked (XXXX XXXX 1234), continuous.
    Cleans newlines that OCR may insert inside the number.
    """
    # Collapse newlines so multi-line numbers become one string
    flat = text.replace("\n", " ")

    # Full spaced 12-digit
    m = re.search(r"\b(\d{4}\s\d{4}\s\d{4})\b", flat)
    if m:
        return m.group(1).strip()

    # Masked: XXXX XXXX 1234
    m = re.search(r"\b([Xx*]{4}\s[Xx*]{4}\s\d{4})\b", flat)
    if m:
        return m.group(1).strip()

    # Continuous 12 digits
    m = re.search(r"\b(\d{12})\b", flat)
    if m:
        return m.group(1)

    # Two groups separated by newline: "XXXX XXXX\nXXXX" -> try in original text
    m = re.search(r"(\d{4}\s\d{4})\s*\n\s*(\d{4})", text)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    return NOT_AVAILABLE


def _extract_pincode(text: str) -> str:
    """Indian PIN codes: 6 digits starting with 1-9."""
    m = re.search(r"\b([1-9]\d{5})\b", text)
    return m.group(1) if m else NOT_AVAILABLE


_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh",
]


def _extract_state(text: str) -> str:
    for state in _STATES:
        if re.search(re.escape(state), text, re.IGNORECASE):
            return state
    return NOT_AVAILABLE


def _extract_city(text: str, state: str, pincode: str) -> str:
    """
    Extract city using two strategies:
    1. Word(s) immediately before the state name in the text.
    2. Word(s) on the same line as the PIN code.
    """
    if state != NOT_AVAILABLE:
        m = re.search(
            r"([A-Za-z\s]{3,30}),?\s*" + re.escape(state),
            text, re.IGNORECASE
        )
        if m:
            candidate = m.group(1).strip().split(",")[-1].strip()
            # Must be a clean alpha word, not OCR garbage
            if re.match(r"^[A-Za-z\s]{3,30}$", candidate):
                return candidate.title()

    if pincode != NOT_AVAILABLE:
        for line in text.splitlines():
            if pincode in line:
                # Remove the pincode and state from the line, what remains is likely city
                city_part = re.sub(re.escape(pincode), "", line)
                if state != NOT_AVAILABLE:
                    city_part = re.sub(re.escape(state), "", city_part, flags=re.IGNORECASE)
                city_part = re.sub(r"[^A-Za-z\s]", "", city_part).strip()
                words = city_part.split()
                if 1 <= len(words) <= 4:
                    return " ".join(words).title()

    return NOT_AVAILABLE


def _extract_address(text: str) -> str:
    """
    Extract address block. Looks for relational prefixes (S/O, W/O, D/O, C/O)
    or 'Address:' label. Caps at 250 chars and strips OCR noise lines.
    """
    patterns = [
        r"(?:Address|pata)\s*[:\-]\s*(.+?)(?:\n\n|\Z)",
        r"(?:S/O|W/O|D/O|C/O)\s*[:\-,]?\s*(.+?)(?:\n\n|\Z)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1)
            # Keep only lines that are mostly ASCII printable (filter Hindi/noise lines)
            clean_lines = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                ascii_ratio = sum(1 for c in line if ord(c) < 128) / max(len(line), 1)
                if ascii_ratio > 0.6 and len(line) > 2:
                    clean_lines.append(line)
                if len(clean_lines) >= 4:  # max 4 address lines
                    break
            if clean_lines:
                return ", ".join(clean_lines)[:250]
    return NOT_AVAILABLE


# ── Per-Image Processor ───────────────────────────────────────────────────────

def _process_image(image_path: Path) -> Dict[str, str]:
    """Run OCR and extract all fields from a single Aadhaar image."""
    log.info("Processing: %s", image_path.name)
    text = _run_ocr(image_path)

    if not text.strip():
        log.warning("No text extracted from %s", image_path.name)
        return {k: NOT_AVAILABLE for k in [
            "File", "Name", "Date of Birth", "Gender",
            "Aadhaar Number", "Address", "City", "State", "Pin Code"
        ]} | {"File": image_path.name}

    state   = _extract_state(text)
    pincode = _extract_pincode(text)

    return {
        "File":           image_path.name,
        "Name":           _extract_name(text),
        "Date of Birth":  _extract_dob(text),
        "Gender":         _extract_gender(text),
        "Aadhaar Number": _extract_aadhaar_number(text),
        "Address":        _extract_address(text),
        "City":           _extract_city(text, state, pincode),
        "State":          state,
        "Pin Code":       pincode,
    }


# ── Public Entry Point ────────────────────────────────────────────────────────

def run() -> None:
    """Process all Aadhaar images in input/aadhaar/ and save to Excel."""
    log.info("=== Task 5: Aadhaar OCR Extractor ===")

    image_files = [
        f for f in sorted(AADHAAR_DIR.iterdir())
        if f.suffix.lower() in IMAGE_EXTENSIONS
    ]

    if not image_files:
        log.error("No image files found in %s", AADHAAR_DIR)
        records_to_excel(
            [{"Note": f"No images found in {AADHAAR_DIR}"}],
            AADHAAR_EXCEL, sheet_name="Aadhaar",
        )
        return

    log.info("Found %d image(s) to process.", len(image_files))
    records: List[Dict[str, str]] = []

    for img_path in image_files:
        try:
            record = _process_image(img_path)
            records.append(record)
            log.info(
                "  %-12s  Name: %-25s | DOB: %-12s | Aadhaar: %-15s | State: %s",
                record["File"], record["Name"], record["Date of Birth"],
                record["Aadhaar Number"], record["State"],
            )
        except Exception as exc:
            log.error("Failed to process %s: %s", img_path.name, exc)
            records.append({
                "File": img_path.name,
                **{k: NOT_AVAILABLE for k in [
                    "Name", "Date of Birth", "Gender", "Aadhaar Number",
                    "Address", "City", "State", "Pin Code"
                ]}
            })

    records_to_excel(records, AADHAAR_EXCEL, sheet_name="Aadhaar")
    log.info("Task 5 complete - %s (%d records)", AADHAAR_EXCEL.name, len(records))
