from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from browser import create_driver
from progress import ProgressTracker
from scraper import SvoeFermerstvoScraper, emails_to_rows


def configure_logging(log_file: Path, verbose: bool) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if verbose:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape emails from svoefermerstvo.ru")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/emails.xlsx"),
        help="Path to the Excel file where results will be stored.",
    )
    parser.add_argument(
        "--progress",
        type=Path,
        default=Path("output/progress.json"),
        help="Path to the JSON file used to persist progress.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("output/parser.log"),
        help="Path to the log file.",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Run the browser in headless mode (default).",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Disable headless mode to see the browser window.",
    )
    parser.set_defaults(headless=True)
    parser.add_argument(
        "--driver-path",
        type=str,
        default=None,
        help="Optional path to the ChromeDriver binary.",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=1.0,
        help="Minimum delay between requests in seconds.",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=3.0,
        help="Maximum delay between requests in seconds.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    configure_logging(args.log_file, args.verbose)

    logging.info("Starting scraper")
    progress_tracker = ProgressTracker(args.progress)

    driver = create_driver(headless=args.headless, driver_path=args.driver_path)
    scraper = SvoeFermerstvoScraper(
        driver=driver,
        progress=progress_tracker,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    try:
        records = scraper.run()
    finally:
        driver.quit()

    rows = emails_to_rows(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=["company_url", "email"])
    df.to_excel(args.output, index=False)

    total_emails = sum(len(record.emails) for record in records)

    logging.info("Scraping completed")
    logging.info("Companies processed: %s", scraper.processed_companies)
    logging.info("Companies with email: %s", scraper.successful_companies)
    logging.info("Companies without email: %s", scraper.missing_email_companies)
    logging.info("Total emails collected: %s", total_emails)


if __name__ == "__main__":
    main()
