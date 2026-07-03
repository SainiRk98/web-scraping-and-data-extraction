"""
utils/helper.py
---------------
Shared utility functions used across all modules:
  - retry decorator
  - Selenium WebDriver factory
  - safe text extraction helpers
"""

import time
import functools
from typing import Callable, Any, Optional

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from config import (
    HEADLESS_BROWSER, PAGE_LOAD_TIMEOUT, IMPLICIT_WAIT,
    MAX_RETRIES, NOT_AVAILABLE,
)
from utils.logger import get_logger

log = get_logger(__name__)


# ── Retry Decorator ───────────────────────────────────────────────────────────

def retry(max_attempts: int = MAX_RETRIES, delay: float = 2.0, exceptions=(Exception,)):
    """
    Decorator that retries a function up to `max_attempts` times on failure.
    Waits `delay` seconds between attempts (exponential back-off × 1.5).
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    log.warning(
                        "Attempt %d/%d failed for '%s': %s",
                        attempt, max_attempts, func.__name__, exc,
                    )
                    if attempt == max_attempts:
                        log.error("All %d attempts exhausted for '%s'.", max_attempts, func.__name__)
                        raise
                    time.sleep(wait)
                    wait *= 1.5
        return wrapper
    return decorator


# ── Selenium WebDriver Factory ────────────────────────────────────────────────

def get_driver(headless: bool = HEADLESS_BROWSER) -> webdriver.Chrome:
    """
    Build and return a Chrome WebDriver instance.
    Uses webdriver-manager to auto-download the correct ChromeDriver.
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.implicitly_wait(IMPLICIT_WAIT)
    log.debug("Chrome WebDriver initialised (headless=%s).", headless)
    return driver


# ── Safe Text Helpers ─────────────────────────────────────────────────────────

def safe_text(element, default: str = NOT_AVAILABLE) -> str:
    """Return stripped text from a BeautifulSoup element, or `default`."""
    try:
        return element.get_text(strip=True) or default
    except Exception:
        return default


def safe_get(data: dict, key: str, default: str = NOT_AVAILABLE) -> str:
    """Return dict value as string, or `default` if missing/empty."""
    val = data.get(key, default)
    return str(val).strip() if val else default


def fetch_page(url: str, headers: Optional[dict] = None, timeout: int = 15) -> Optional[str]:
    """
    Perform an HTTP GET and return the response text.
    Returns None on failure.
    """
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    if headers:
        default_headers.update(headers)
    try:
        resp = requests.get(url, headers=default_headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        log.error("HTTP GET failed for %s: %s", url, exc)
        return None
