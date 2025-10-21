"""Utilities for creating and configuring Selenium WebDriver instances."""
from __future__ import annotations

import logging
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

LOGGER = logging.getLogger(__name__)


def create_driver(headless: bool = True, driver_path: Optional[str] = None) -> webdriver.Chrome:
    """Create a configured Chrome WebDriver instance.

    Parameters
    ----------
    headless:
        If ``True`` (default), start the browser in headless mode. Disable this to debug
        issues visually.
    driver_path:
        Optional path to the ChromeDriver binary. When ``None`` Selenium attempts to
        locate the driver in ``PATH``.
    """

    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    if headless:
        # ``--headless=new`` enables the latest headless implementation.
        chrome_options.add_argument("--headless=new")
        LOGGER.debug("Browser will run in headless mode")
    else:
        LOGGER.debug("Browser will run with UI enabled")

    if driver_path:
        LOGGER.debug("Using explicit ChromeDriver path: %s", driver_path)
        driver = webdriver.Chrome(driver_path, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    driver.set_page_load_timeout(60)
    return driver
