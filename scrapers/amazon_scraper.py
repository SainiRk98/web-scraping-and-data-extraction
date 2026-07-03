"""
scrapers/amazon_scraper.py
---------------------------
Task 2 – Search Amazon India for "Table Fan" and extract detailed
product information from each product page.

Extracted fields:
  Product Name, ASIN, Price, Dimensions, Weight,
  Manufacturer, Warranty, Features, Color, Other Info

Number of products to scrape is controlled by AMAZON_MAX_PRODUCTS in config.py
(or the AMAZON_MAX_PRODUCTS environment variable).
"""

import re
import time
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import (
    AMAZON_BASE_URL, AMAZON_SEARCH_KW, AMAZON_MAX_PRODUCTS,
    NOT_AVAILABLE, EXPLICIT_WAIT, AMAZON_EXCEL,
)
from utils.helper import get_driver, safe_text, retry
from utils.excel_writer import records_to_excel
from utils.logger import get_logger

log = get_logger(__name__)


# ── Product Detail Extractor ──────────────────────────────────────────────────

def _extract_tech_detail(soup: BeautifulSoup, label: str) -> str:
    """
    Search the 'Technical Details' / 'Product Information' table for a row
    whose header matches `label` (case-insensitive) and return its value.
    """
    label_lower = label.lower()
    # Try <table> rows first
    for row in soup.select("table.prodDetTable tr, #productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr"):
        th = row.find("th") or row.find("td")
        td_all = row.find_all("td")
        if th and td_all:
            if label_lower in th.get_text(strip=True).lower():
                return td_all[-1].get_text(strip=True) or NOT_AVAILABLE
    # Try <li> detail bullets
    for li in soup.select("#detailBullets_feature_div li, .detail-bullet-list li"):
        text = li.get_text(" ", strip=True)
        if label_lower in text.lower():
            parts = text.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip() or NOT_AVAILABLE
    return NOT_AVAILABLE


def _extract_product_details(driver, url: str) -> Dict[str, Any]:
    """
    Navigate to a product page and extract all required fields.
    Returns a dict with all fields; missing ones default to NOT_AVAILABLE.
    """
    log.debug("Visiting product page: %s", url)
    try:
        driver.get(url)
        wait = WebDriverWait(driver, EXPLICIT_WAIT)
        wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
    except TimeoutException:
        log.warning("Timeout loading product page: %s", url)
        return {"URL": url, "Note": "Page load timeout"}

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # ── Product Name ──────────────────────────────────────────────────────────
    name = safe_text(soup.select_one("#productTitle"))

    # ── ASIN ──────────────────────────────────────────────────────────────────
    asin = NOT_AVAILABLE
    # Try URL pattern first
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if asin_match:
        asin = asin_match.group(1)
    else:
        asin = _extract_tech_detail(soup, "ASIN")

    # ── Price ─────────────────────────────────────────────────────────────────
    price = (
        safe_text(soup.select_one(".a-price .a-offscreen"))
        or safe_text(soup.select_one("#priceblock_ourprice"))
        or safe_text(soup.select_one("#priceblock_dealprice"))
        or safe_text(soup.select_one(".a-price-whole"))
        or NOT_AVAILABLE
    )

    # ── Technical Details ─────────────────────────────────────────────────────
    dimensions   = _extract_tech_detail(soup, "dimension")
    weight       = _extract_tech_detail(soup, "weight")
    manufacturer = _extract_tech_detail(soup, "manufacturer")
    color        = (
        _extract_tech_detail(soup, "colour")
        or _extract_tech_detail(soup, "color")
    )
    warranty = (
        _extract_tech_detail(soup, "warranty")
        or safe_text(soup.select_one("#warranty-support-feature"))
    )

    # ── Bullet Features ───────────────────────────────────────────────────────
    feature_bullets = soup.select("#feature-bullets li span.a-list-item")
    features = " | ".join(
        b.get_text(strip=True) for b in feature_bullets
        if b.get_text(strip=True)
    ) or NOT_AVAILABLE

    # ── Other Info (rating, review count, availability) ───────────────────────
    rating       = safe_text(soup.select_one("#acrPopover span.a-icon-alt"))
    review_count = safe_text(soup.select_one("#acrCustomerReviewText"))
    availability = safe_text(soup.select_one("#availability span"))
    other_info   = f"Rating: {rating} | Reviews: {review_count} | Availability: {availability}"

    return {
        "Product Name":      name,
        "ASIN":              asin,
        "Price":             price,
        "Dimensions":        dimensions,
        "Weight":            weight,
        "Manufacturer":      manufacturer,
        "Warranty":          warranty,
        "Features":          features,
        "Color":             color,
        "Other Info":        other_info,
        "URL":               url,
    }


# ── Search Results Collector ──────────────────────────────────────────────────

def _collect_product_urls(driver, max_products: int) -> List[str]:
    """
    Search Amazon for AMAZON_SEARCH_KW and collect product page URLs
    until `max_products` unique URLs are gathered (across pages).
    """
    log.info("Searching Amazon for '%s' (max %d products).", AMAZON_SEARCH_KW, max_products)
    urls: List[str] = []
    wait = WebDriverWait(driver, EXPLICIT_WAIT)

    driver.get(AMAZON_BASE_URL)

    # Handle potential bot-check / captcha page
    try:
        search_box = wait.until(EC.presence_of_element_located((By.ID, "twotabsearchtextbox")))
        search_box.clear()
        search_box.send_keys(AMAZON_SEARCH_KW)
        search_box.send_keys(Keys.RETURN)
    except TimeoutException:
        log.error("Amazon search box not found – possible CAPTCHA or block.")
        return urls

    page_num = 1
    while len(urls) < max_products:
        log.debug("Amazon search results page %d", page_num)
        try:
            wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
            ))
        except TimeoutException:
            log.warning("Search results not loaded on page %d.", page_num)
            break

        soup = BeautifulSoup(driver.page_source, "html.parser")
        result_divs = soup.select("div[data-component-type='s-search-result']")

        for div in result_divs:
            if len(urls) >= max_products:
                break
            link = div.select_one("a.a-link-normal.s-no-outline, h2 a.a-link-normal")
            if link and link.get("href"):
                href = link["href"]
                full_url = href if href.startswith("http") else AMAZON_BASE_URL + href
                # Keep only /dp/ product pages
                if "/dp/" in full_url and full_url not in urls:
                    urls.append(full_url)

        log.info("Collected %d/%d product URLs so far.", len(urls), max_products)

        if len(urls) >= max_products:
            break

        # Go to next page
        try:
            next_btn = driver.find_element(
                By.CSS_SELECTOR,
                "a.s-pagination-next, li.a-last a"
            )
            driver.execute_script("arguments[0].click();", next_btn)
            wait.until(EC.staleness_of(next_btn))
            page_num += 1
        except NoSuchElementException:
            log.info("No more search result pages.")
            break

    return urls[:max_products]


# ── Public Entry Point ────────────────────────────────────────────────────────

@retry(max_attempts=2, delay=5)
def run(max_products: int = AMAZON_MAX_PRODUCTS) -> None:
    """
    Run the Amazon scraper:
      1. Search for Table Fan
      2. Collect product URLs
      3. Visit each product page and extract details
      4. Save to Excel
    """
    log.info("=== Task 2: Amazon Scraper (max=%d) ===", max_products)
    driver = get_driver(headless=True)
    records: List[Dict[str, Any]] = []

    try:
        product_urls = _collect_product_urls(driver, max_products)
        log.info("Found %d product URLs. Extracting details...", len(product_urls))

        for idx, url in enumerate(product_urls, start=1):
            log.info("Processing product %d/%d", idx, len(product_urls))
            try:
                details = _extract_product_details(driver, url)
                records.append(details)
            except Exception as exc:
                log.error("Failed to extract product %d (%s): %s", idx, url, exc)
                records.append({
                    "Product Name": NOT_AVAILABLE,
                    "ASIN": NOT_AVAILABLE,
                    "URL": url,
                    "Note": str(exc),
                })
            # Small polite delay to avoid rate-limiting
            time.sleep(1.5)

    finally:
        driver.quit()

    records_to_excel(records, AMAZON_EXCEL, sheet_name="Table Fans")
    log.info("Task 2 complete → %s (%d records)", AMAZON_EXCEL.name, len(records))
