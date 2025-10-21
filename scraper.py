"""High level scraper implementation for svoefermerstvo.ru."""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .progress import ProgressTracker

LOGGER = logging.getLogger(__name__)

CATALOG_URL = "https://svoefermerstvo.ru/companies/root"
COMPANY_LINK_SELECTOR = 'a[href*="/organization/"]'
WAIT_TIMEOUT = 25


@dataclass
class CompanyEmails:
    url: str
    emails: Sequence[str]


class SvoeFermerstvoScraper:
    def __init__(
        self,
        driver: WebDriver,
        progress: ProgressTracker,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
    ) -> None:
        self.driver = driver
        self.progress = progress
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.wait = WebDriverWait(self.driver, WAIT_TIMEOUT)
        self.processed_companies = 0
        self.successful_companies = 0
        self.missing_email_companies = 0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def run(self) -> List[CompanyEmails]:
        results: List[CompanyEmails] = []
        self.processed_companies = 0
        self.successful_companies = 0
        self.missing_email_companies = 0

        total_pages = self._determine_total_pages()
        LOGGER.info("Total pages discovered: %s", total_pages)

        start_page = max(1, self.progress.state.page_index)
        for page in range(start_page, total_pages + 1):
            self.progress.mark_page_started(page)
            LOGGER.info("Processing page %s/%s", page, total_pages)
            company_links = self._collect_company_links(page)
            LOGGER.debug("Found %s company links on page %s", len(company_links), page)

            start_index = self.progress.state.card_index + 1 if page == start_page else 0
            for idx, link in enumerate(company_links):
                if idx < start_index:
                    continue

                if link in (self.progress.state.processed_urls or set()):
                    LOGGER.debug("Skipping already processed company: %s", link)
                    continue

                try:
                    company_emails = self._process_company(link)
                except WebDriverException as exc:
                    LOGGER.error("WebDriver error processing %s: %s", link, exc)
                    continue

                self.processed_companies += 1
                if company_emails:
                    results.append(company_emails)
                    self.successful_companies += 1
                    LOGGER.info(
                        "Collected %s email(s) from %s", len(company_emails.emails), link
                    )
                else:
                    self.missing_email_companies += 1
                    LOGGER.info("No emails found for %s", link)

                self.progress.mark_card_processed(page, idx, link)
                self._random_delay()

        return results

    # ------------------------------------------------------------------
    # individual steps
    # ------------------------------------------------------------------
    def _determine_total_pages(self) -> int:
        self.driver.get(CATALOG_URL)
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, COMPANY_LINK_SELECTOR)))
        LOGGER.debug("Catalog page loaded, retrieving pagination numbers")

        pagination_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="page="]')
        page_numbers = []
        for element in pagination_elements:
            text = element.text.strip()
            if text.isdigit():
                page_numbers.append(int(text))

        if not page_numbers:
            LOGGER.warning("Pagination numbers not found, defaulting to 1 page")
            return 1

        return max(page_numbers)

    def _collect_company_links(self, page_number: int) -> List[str]:
        page_url = CATALOG_URL if page_number == 1 else f"{CATALOG_URL}?page={page_number}"
        LOGGER.debug("Loading catalog page: %s", page_url)
        self.driver.get(page_url)
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, COMPANY_LINK_SELECTOR)))

        elements = self.driver.find_elements(By.CSS_SELECTOR, COMPANY_LINK_SELECTOR)
        links = []
        for element in elements:
            try:
                href = element.get_attribute("href")
            except WebDriverException:
                continue
            if href and "/organization/" in href:
                links.append(href.split("#")[0])

        unique_links = list(dict.fromkeys(links))
        LOGGER.debug("Collected %s unique company links", len(unique_links))
        return unique_links

    def _process_company(self, url: str) -> Optional[CompanyEmails]:
        LOGGER.info("Processing company page: %s", url)
        self.driver.get(url)
        self._handle_popups()

        if not self._open_addresses_tab():
            LOGGER.warning("Could not open 'Адреса и доставка' for %s", url)
            return None

        emails = self._extract_emails()
        if not emails:
            return None

        return CompanyEmails(url=url, emails=emails)

    def _handle_popups(self) -> None:
        """Dismiss cookie or region popups when present."""
        popup_selectors = [
            'button[aria-label*="закрыть" i]',
            'button[aria-label*="close" i]',
            'button[data-testid="close-modal"]',
            'button[title="Закрыть"]',
        ]

        for selector in popup_selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                try:
                    element.click()
                    LOGGER.debug("Closed popup via selector %s", selector)
                except WebDriverException:
                    continue

        # Sometimes the cookie banner is an "Accept" button.
        accept_selectors = [
            '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "принимаю")]',
            '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "согласен")]'
        ]
        for xpath in accept_selectors:
            elements = self.driver.find_elements(By.XPATH, xpath)
            for element in elements:
                try:
                    element.click()
                    LOGGER.debug("Accepted popup via xpath %s", xpath)
                except WebDriverException:
                    continue

    def _open_addresses_tab(self) -> bool:
        try:
            tab = self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//button[contains(., "Адреса и доставка")] | '
                        '//a[contains(., "Адреса и доставка")]'
                    )
                )
            )
        except TimeoutException:
            LOGGER.error("'Адреса и доставка' tab not found")
            return False

        try:
            tab.click()
        except WebDriverException:
            LOGGER.debug("Falling back to JavaScript click for tab")
            self.driver.execute_script("arguments[0].click();", tab)

        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//div[contains(@class, "point") or contains(@class, "address")]'
                        ' | //a[starts-with(@href, "mailto:")]'
                    )
                )
            )
        except TimeoutException:
            LOGGER.warning("Addresses section did not load")
            return False

        return True

    def _extract_emails(self) -> Sequence[str]:
        email_elements = self.driver.find_elements(By.XPATH, '//a[starts-with(@href, "mailto:")]')
        emails = set()
        for element in email_elements:
            try:
                href = element.get_attribute("href") or ""
                text = element.text.strip()
            except WebDriverException:
                continue

            if href.startswith("mailto:"):
                emails.add(href.split(":", 1)[1])
            if "@" in text:
                emails.add(text)

        # fallback: look for plain text containing '@'
        if not emails:
            text_nodes = self.driver.find_elements(
                By.XPATH,
                '//*[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "@")]'
            )
            for node in text_nodes:
                try:
                    text = node.text.strip()
                except WebDriverException:
                    continue
                if "@" in text:
                    parts = [part for part in text.replace(";", ",").split() if "@" in part]
                    for part in parts:
                        cleaned = part.strip().strip(',.;')
                        if "@" in cleaned:
                            emails.add(cleaned)

        return sorted(emails)

    def _random_delay(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        LOGGER.debug("Sleeping for %.2f seconds", delay)
        time.sleep(delay)


def emails_to_rows(records: Iterable[CompanyEmails]) -> List[dict]:
    rows: List[dict] = []
    for record in records:
        email_value = ", ".join(record.emails)
        rows.append({"company_url": record.url, "email": email_value})
    return rows
