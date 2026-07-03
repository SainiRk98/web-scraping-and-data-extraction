"""
scrapers/instagram_scraper.py
------------------------------
Task 3 – Extract data from a user-specified Instagram post.

Extracted fields:
  Number of Likes, Number of Comments,
  Commenter Username, Comment Content

Credentials are read from environment variables:
  INSTAGRAM_USERNAME  – your Instagram login username / email
  INSTAGRAM_PASSWORD  – your Instagram login password
  INSTAGRAM_POST_URL  – full URL of the post to scrape

How to set environment variables (Windows):
  set INSTAGRAM_USERNAME=your_username
  set INSTAGRAM_PASSWORD=your_password
  set INSTAGRAM_POST_URL=https://www.instagram.com/p/XXXXXXXXXX/

IMPORTANT: Never hardcode credentials. Always use environment variables.

Note: Instagram aggressively blocks automated access. This scraper uses
Selenium with human-like delays and waits. If Instagram shows a CAPTCHA
or blocks the session, manual intervention may be required.
"""

import time
import os
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

from config import (
    INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_POST_URL,
    NOT_AVAILABLE, EXPLICIT_WAIT, INSTAGRAM_EXCEL,
)
from utils.helper import get_driver
from utils.excel_writer import records_to_excel
from utils.logger import get_logger

log = get_logger(__name__)

INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"


# ── Login ─────────────────────────────────────────────────────────────────────

def _login(driver) -> bool:
    """
    Log in to Instagram using credentials from environment variables.
    Returns True on success, False on failure.
    """
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        log.error(
            "Instagram credentials not set. "
            "Please set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables."
        )
        return False

    log.info("Logging in to Instagram as '%s'...", INSTAGRAM_USERNAME)
    wait = WebDriverWait(driver, EXPLICIT_WAIT)

    try:
        driver.get(INSTAGRAM_LOGIN_URL)

        # Accept cookies if prompted
        try:
            cookie_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Allow') or contains(text(),'Accept')]"))
            )
            cookie_btn.click()
        except TimeoutException:
            pass

        # Enter username
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        username_field.clear()
        username_field.send_keys(INSTAGRAM_USERNAME)

        # Enter password
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(INSTAGRAM_PASSWORD)

        # Click login
        login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_btn.click()

        # Wait for home feed or error
        time.sleep(5)

        # Dismiss "Save Login Info" popup if it appears
        try:
            not_now = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Not Now') or contains(text(),'Not now')]"))
            )
            not_now.click()
        except TimeoutException:
            pass

        # Dismiss notifications popup
        try:
            not_now2 = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Not Now') or contains(text(),'Not now')]"))
            )
            not_now2.click()
        except TimeoutException:
            pass

        log.info("Instagram login successful.")
        return True

    except Exception as exc:
        log.error("Instagram login failed: %s", exc)
        return False


# ── Post Data Extractor ───────────────────────────────────────────────────────

def _extract_likes(driver) -> str:
    """Extract like count from the post page."""
    selectors = [
        "section span[class*='like'] span",
        "button[class*='like'] span",
        "span[class*='_aacl']",
        "//span[contains(@class,'like')]//span",
    ]
    for sel in selectors:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            if text:
                return text
        except NoSuchElementException:
            continue
    # Try aria-label on like button
    try:
        like_btn = driver.find_element(By.XPATH, "//button[contains(@aria-label,'like') or contains(@aria-label,'Like')]")
        return like_btn.get_attribute("aria-label") or NOT_AVAILABLE
    except NoSuchElementException:
        return NOT_AVAILABLE


def _load_all_comments(driver, wait: WebDriverWait) -> None:
    """Click 'Load more comments' repeatedly until all comments are visible."""
    max_clicks = 50
    for _ in range(max_clicks):
        try:
            load_more = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//span[contains(text(),'Load more comments') or contains(text(),'View more comments')]"
                    "/ancestor::button | "
                    "//button[contains(@aria-label,'Load more')]"
                ))
            )
            driver.execute_script("arguments[0].click();", load_more)
            time.sleep(1.5)
        except TimeoutException:
            break


def _extract_comments(driver) -> List[Dict[str, Any]]:
    """Parse all visible comments and return list of {username, comment} dicts."""
    soup = BeautifulSoup(driver.page_source, "html.parser")
    comments: List[Dict[str, Any]] = []

    # Instagram comment structure (may change with UI updates)
    comment_blocks = soup.select("ul li[role='menuitem'], ul._a9ym li, div._a9zs")

    for block in comment_blocks:
        username_tag = block.select_one("a[href*='/'] span, h3 a, span._aap6")
        comment_tag  = block.select_one("span._aap6 ~ span, div._a9zr span, span[class*='comment']")

        username = username_tag.get_text(strip=True) if username_tag else NOT_AVAILABLE
        comment  = comment_tag.get_text(strip=True)  if comment_tag  else NOT_AVAILABLE

        if username != NOT_AVAILABLE or comment != NOT_AVAILABLE:
            comments.append({"Username": username, "Comment": comment})

    return comments


# ── Public Entry Point ────────────────────────────────────────────────────────

def run(post_url: str = "") -> None:
    """
    Run the Instagram scraper for the given post URL.
    Falls back to INSTAGRAM_POST_URL from config/env if not provided.
    """
    log.info("=== Task 3: Instagram Scraper ===")

    target_url = post_url or INSTAGRAM_POST_URL
    if not target_url:
        log.error(
            "No Instagram post URL provided. "
            "Set INSTAGRAM_POST_URL environment variable or pass it as argument."
        )
        records_to_excel(
            [{"Note": "No post URL provided. Set INSTAGRAM_POST_URL env variable."}],
            INSTAGRAM_EXCEL,
            sheet_name="Instagram",
        )
        return

    # Run with non-headless so Instagram is less likely to block
    driver = get_driver(headless=False)
    wait   = WebDriverWait(driver, EXPLICIT_WAIT)

    try:
        # Login
        if not _login(driver):
            records_to_excel(
                [{"Note": "Login failed. Check INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD."}],
                INSTAGRAM_EXCEL,
                sheet_name="Instagram",
            )
            return

        # Navigate to post
        log.info("Navigating to post: %s", target_url)
        driver.get(target_url)

        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
        except TimeoutException:
            log.error("Post page did not load: %s", target_url)
            return

        # Extract likes
        likes = _extract_likes(driver)
        log.info("Likes: %s", likes)

        # Load all comments
        _load_all_comments(driver, wait)

        # Extract comments
        comments = _extract_comments(driver)
        log.info("Extracted %d comments.", len(comments))

        # Build records
        records: List[Dict[str, Any]] = []
        for c in comments:
            records.append({
                "Post URL":          target_url,
                "Likes":             likes,
                "Total Comments":    str(len(comments)),
                "Commenter Username": c["Username"],
                "Comment Content":   c["Comment"],
            })

        if not records:
            records = [{
                "Post URL":       target_url,
                "Likes":          likes,
                "Total Comments": "0",
                "Commenter Username": NOT_AVAILABLE,
                "Comment Content":   NOT_AVAILABLE,
            }]

        records_to_excel(records, INSTAGRAM_EXCEL, sheet_name="Instagram")
        log.info("Task 3 complete → %s (%d rows)", INSTAGRAM_EXCEL.name, len(records))

    except Exception as exc:
        log.error("Instagram scraper error: %s", exc)
        records_to_excel(
            [{"Note": f"Scraper error: {exc}"}],
            INSTAGRAM_EXCEL,
            sheet_name="Instagram",
        )
    finally:
        driver.quit()
