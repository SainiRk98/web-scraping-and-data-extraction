"""
scrapers/property_scraper.py
-----------------------------
Task 1 - Scrape property listings from:
  1. https://www.gray-point.com/index.php/experience  (correct URL)
  2. https://www.rightmove.co.uk/commercial-property  (search page)

GrayPoint:
  - Lists properties at /index.php/experience
  - Each card links to /index.php/experience/view/<slug>
  - Detail page has a table with Service, Property type, Area, Rent

Rightmove:
  - Uses Selenium to load the JS-rendered search results
  - Extracts data from rendered property cards

Extracted fields: Name, Address, Features, Price/Rate, Other Info
"""

import time
from typing import List, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import NOT_AVAILABLE, EXPLICIT_WAIT, PROPERTY_EXCEL
from utils.helper import get_driver, safe_text, fetch_page, retry
from utils.excel_writer import records_to_excel
from utils.logger import get_logger

log = get_logger(__name__)

GRAYPOINT_BASE    = "https://www.gray-point.com"
GRAYPOINT_LIST    = "https://www.gray-point.com/index.php/experience"
RIGHTMOVE_SEARCH  = "https://www.rightmove.co.uk/commercial-property-to-let.html"


# ── GrayPoint ─────────────────────────────────────────────────────────────────

def _scrape_graypoint_detail(url: str) -> Dict[str, Any]:
    """
    Fetch a single GrayPoint property detail page and extract fields
    from the info table (Service, Property type, Area, Rent).
    """
    html = fetch_page(url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    data: Dict[str, Any] = {}

    # Info table: <td class="left">Label</td><td><strong>Value</strong></td>
    for row in soup.select(".property-info table tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            if "service" in label:
                data["Features"] = value
            elif "property" in label:
                data["Other Info"] = value
            elif "area" in label:
                data["Address"] = value
            elif "rent" in label or "price" in label:
                data["Price/Rate"] = value

    # Description paragraph
    desc = soup.select_one(".page-text p")
    if desc:
        existing_other = data.get("Other Info", "")
        prop_type = existing_other
        desc_text = desc.get_text(strip=True)
        data["Other Info"] = f"{prop_type} | {desc_text}" if prop_type else desc_text

    return data


@retry(max_attempts=3, delay=3)
def scrape_graypoint() -> List[Dict[str, Any]]:
    """
    Scrape all property listings from gray-point.com/index.php/experience.
    Visits each detail page to collect full information.
    """
    log.info("Starting GrayPoint scraper -> %s", GRAYPOINT_LIST)
    records: List[Dict[str, Any]] = []

    # Collect all service filter URLs (All, Freehold Sales, Portfolio Mgmt, etc.)
    html = fetch_page(GRAYPOINT_LIST)
    if not html:
        log.error("Could not fetch GrayPoint listing page.")
        return records

    soup = BeautifulSoup(html, "html.parser")

    # Collect all property card links from the listing page
    card_links = []
    for a in soup.select(".items-listing a[href*='/experience/view/']"):
        href = a.get("href", "")
        full_url = href if href.startswith("http") else urljoin(GRAYPOINT_BASE, href)
        if full_url not in card_links:
            card_links.append(full_url)

    # Also check filter pages (Freehold Sales, Portfolio Management, etc.)
    filter_urls = []
    for opt in soup.select("select option[value*='/experience/service/']"):
        val = opt.get("value", "")
        if val:
            filter_urls.append(val if val.startswith("http") else urljoin(GRAYPOINT_BASE, val))

    for filter_url in filter_urls:
        fhtml = fetch_page(filter_url)
        if not fhtml:
            continue
        fsoup = BeautifulSoup(fhtml, "html.parser")
        for a in fsoup.select(".items-listing a[href*='/experience/view/']"):
            href = a.get("href", "")
            full_url = href if href.startswith("http") else urljoin(GRAYPOINT_BASE, href)
            if full_url not in card_links:
                card_links.append(full_url)

    log.info("GrayPoint: found %d property detail pages.", len(card_links))

    for url in card_links:
        # Extract name from URL slug
        slug = url.rstrip("/").split("/")[-1]
        name = slug.replace("-", " ").title()

        detail = _scrape_graypoint_detail(url)
        record = {
            "Source":     "GrayPoint",
            "Name":       name,
            "Address":    detail.get("Address", NOT_AVAILABLE),
            "Features":   detail.get("Features", NOT_AVAILABLE),
            "Price/Rate": detail.get("Price/Rate", NOT_AVAILABLE),
            "Other Info": detail.get("Other Info", NOT_AVAILABLE),
            "URL":        url,
        }
        records.append(record)
        log.info("  GrayPoint: %s | Area: %s | Rent: %s",
                 name, record["Address"], record["Price/Rate"])

    log.info("GrayPoint scraper finished. Total: %d records.", len(records))
    return records


# ── Rightmove ─────────────────────────────────────────────────────────────────

def _parse_rightmove_card(card) -> Dict[str, Any]:
    """Parse a single Rightmove property card from BeautifulSoup."""
    # Try multiple selector patterns for each field
    name = (
        safe_text(card.select_one("h2, h3, [class*='title'], [class*='address']"))
    )
    address = (
        safe_text(card.select_one("address, [class*='address'], [data-test='address']"))
        or name
    )
    price = (
        safe_text(card.select_one("[class*='price'], [data-test='price'], .price"))
    )
    features_tags = card.select("[class*='feature'], [class*='detail'] span, li")
    features = " | ".join(t.get_text(strip=True) for t in features_tags[:5]) or NOT_AVAILABLE

    link = card.select_one("a[href]")
    url = ("https://www.rightmove.co.uk" + link["href"]) if link and link.get("href", "").startswith("/") else (link["href"] if link else NOT_AVAILABLE)

    return {
        "Source":     "Rightmove",
        "Name":       name,
        "Address":    address,
        "Features":   features,
        "Price/Rate": price,
        "Other Info": NOT_AVAILABLE,
        "URL":        url,
    }


@retry(max_attempts=2, delay=5)
def scrape_rightmove() -> List[Dict[str, Any]]:
    """
    Scrape Rightmove commercial property listings using Selenium.
    Accepts cookies, waits for JS to render, then parses cards.
    """
    log.info("Starting Rightmove scraper -> %s", RIGHTMOVE_SEARCH)
    records: List[Dict[str, Any]] = []
    driver = get_driver(headless=False)  # non-headless reduces bot detection

    try:
        driver.get(RIGHTMOVE_SEARCH)
        wait = WebDriverWait(driver, EXPLICIT_WAIT)

        # Accept cookies
        try:
            accept = wait.until(EC.element_to_be_clickable(
                (By.ID, "onetrust-accept-btn-handler")
            ))
            accept.click()
            log.debug("Rightmove: accepted cookies.")
            time.sleep(2)
        except TimeoutException:
            log.debug("Rightmove: no cookie banner.")

        # Wait for any content to load
        time.sleep(6)

        page_num = 1
        while True:
            log.info("Rightmove: parsing page %d ...", page_num)
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Try all known card selectors
            cards = (
                soup.select("div[data-test='propertyCard']")
                or soup.select("div[class*='propertyCard']")
                or soup.select("li[class*='propertyCard']")
                or soup.select("article[class*='property']")
                or soup.select("[class*='l-searchResult']")
                or soup.select("[class*='search-result']")
            )

            if not cards:
                # Try extracting from JSON embedded in page
                import re, json
                json_matches = re.findall(
                    r'"address"\s*:\s*"([^"]+)".*?"price"\s*:\s*"([^"]+)"',
                    driver.page_source
                )
                if json_matches:
                    for addr, price in json_matches[:20]:
                        records.append({
                            "Source":     "Rightmove",
                            "Name":       addr,
                            "Address":    addr,
                            "Features":   NOT_AVAILABLE,
                            "Price/Rate": price,
                            "Other Info": NOT_AVAILABLE,
                            "URL":        RIGHTMOVE_SEARCH,
                        })
                    log.info("Rightmove: extracted %d records from JSON.", len(json_matches))
                else:
                    log.warning("Rightmove: no property cards found on page %d.", page_num)
                break

            for card in cards:
                records.append(_parse_rightmove_card(card))

            log.info("Rightmove: page %d -> %d cards", page_num, len(cards))

            # Try next page
            try:
                next_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "button[data-test='pagination-next'], "
                    "a.pagination-direction--next, "
                    "[class*='pagination'][class*='next']"
                )
                if not next_btn.is_enabled():
                    break
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(4)
                page_num += 1
            except NoSuchElementException:
                log.info("Rightmove: no more pages after page %d.", page_num)
                break

    except Exception as exc:
        log.error("Rightmove scraper error: %s", exc)
    finally:
        driver.quit()

    log.info("Rightmove scraper finished. Total: %d records.", len(records))
    return records


# ── Public Entry Point ────────────────────────────────────────────────────────

def run() -> None:
    """Run both property scrapers and save combined results to Excel."""
    log.info("=== Task 1: Property Scraper ===")
    all_records: List[Dict[str, Any]] = []

    try:
        all_records.extend(scrape_graypoint())
    except Exception as exc:
        log.error("GrayPoint scraper failed: %s", exc)

    try:
        all_records.extend(scrape_rightmove())
    except Exception as exc:
        log.error("Rightmove scraper failed: %s", exc)

    if all_records:
        records_to_excel(all_records, PROPERTY_EXCEL, sheet_name="Properties")
        log.info("Task 1 complete -> %s (%d records)", PROPERTY_EXCEL.name, len(all_records))
    else:
        log.warning("Task 1: No property records extracted.")
        records_to_excel(
            [{"Note": "No data extracted - check selectors or site availability"}],
            PROPERTY_EXCEL, sheet_name="Properties",
        )
