"""
main.py
-------
Entry point for the Data Extraction project.

Usage:
    # Run all tasks
    python main.py

    # Run specific tasks only
    python main.py --tasks 1 4 5

    # Amazon: override max products at runtime
    python main.py --tasks 2 --max-products 30

    # Instagram: pass post URL at runtime
    python main.py --tasks 3 --post-url https://www.instagram.com/p/XXXXXXXXXX/

Environment variables (set before running):
    INSTAGRAM_USERNAME   – Instagram login username
    INSTAGRAM_PASSWORD   – Instagram login password
    INSTAGRAM_POST_URL   – Instagram post URL (alternative to --post-url)
    AMAZON_MAX_PRODUCTS  – Number of Amazon products to scrape (default 20)
    TESSERACT_CMD        – Path to tesseract.exe (Windows)
    LOG_LEVEL            – DEBUG | INFO | WARNING | ERROR  (default INFO)
"""

import argparse
import sys

from utils.logger import get_logger

log = get_logger("main")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Data Extraction Project – runs all 5 extraction tasks."
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=[1, 2, 3, 4, 5],
        help="Which tasks to run (default: all). E.g. --tasks 1 4 5",
    )
    parser.add_argument(
        "--max-products",
        type=int,
        default=None,
        help="Override AMAZON_MAX_PRODUCTS for Task 2.",
    )
    parser.add_argument(
        "--post-url",
        type=str,
        default="",
        help="Instagram post URL for Task 3 (overrides INSTAGRAM_POST_URL env var).",
    )
    return parser.parse_args()


def run_task_1():
    log.info("──────────────────────────────────────────")
    log.info("TASK 1 – Property Scraper")
    log.info("──────────────────────────────────────────")
    from scrapers.property_scraper import run
    run()


def run_task_2(max_products=None):
    log.info("──────────────────────────────────────────")
    log.info("TASK 2 – Amazon Product Scraper")
    log.info("──────────────────────────────────────────")
    from scrapers.amazon_scraper import run
    from config import AMAZON_MAX_PRODUCTS
    run(max_products=max_products or AMAZON_MAX_PRODUCTS)


def run_task_3(post_url=""):
    log.info("──────────────────────────────────────────")
    log.info("TASK 3 – Instagram Post Scraper")
    log.info("──────────────────────────────────────────")
    from scrapers.instagram_scraper import run
    run(post_url=post_url)


def run_task_4():
    log.info("──────────────────────────────────────────")
    log.info("TASK 4 – PDF Table Extractor")
    log.info("──────────────────────────────────────────")
    from extractors.pdf_extractor import run
    run()


def run_task_5():
    log.info("──────────────────────────────────────────")
    log.info("TASK 5 – Aadhaar OCR Extractor")
    log.info("──────────────────────────────────────────")
    from extractors.aadhaar_extractor import run
    run()


TASK_MAP = {
    1: run_task_1,
    2: run_task_2,
    3: run_task_3,
    4: run_task_4,
    5: run_task_5,
}


def main():
    args = parse_args()
    log.info("========================================")
    log.info("  Data Extraction Project – Starting")
    log.info("  Tasks to run: %s", args.tasks)
    log.info("========================================")

    failed_tasks = []

    for task_num in sorted(args.tasks):
        try:
            if task_num == 2:
                TASK_MAP[task_num](max_products=args.max_products)
            elif task_num == 3:
                TASK_MAP[task_num](post_url=args.post_url)
            else:
                TASK_MAP[task_num]()
        except Exception as exc:
            log.error("Task %d failed with unhandled exception: %s", task_num, exc, exc_info=True)
            failed_tasks.append(task_num)

    log.info("========================================")
    if failed_tasks:
        log.warning("Completed with errors in tasks: %s", failed_tasks)
    else:
        log.info("All tasks completed successfully.")
    log.info("Check the output/ directory for Excel files.")
    log.info("========================================")


if __name__ == "__main__":
    main()
