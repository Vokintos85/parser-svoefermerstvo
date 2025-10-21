"""Utilities for tracking scraping progress on disk."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, Set

LOGGER = logging.getLogger(__name__)


@dataclass
class ProgressState:
    """Represents the progress of the scraper.

    Attributes
    ----------
    page_index:
        Current page index in the pagination (1-indexed).
    card_index:
        Index of the last processed card on the page (0-indexed). ``-1`` means the
        page was not started yet.
    processed_urls:
        Set of company URLs that have already been scraped.
    """

    page_index: int = 1
    card_index: int = -1
    processed_urls: Set[str] | None = None

    def to_json(self) -> Dict[str, object]:
        data = asdict(self)
        data["processed_urls"] = sorted(self.processed_urls or [])
        return data

    @classmethod
    def from_json(cls, data: Dict[str, object]) -> "ProgressState":
        return cls(
            page_index=int(data.get("page_index", 1)),
            card_index=int(data.get("card_index", -1)),
            processed_urls=set(data.get("processed_urls", [])),
        )


class ProgressTracker:
    """Handles persistence of :class:`ProgressState`."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.state: ProgressState = ProgressState()
        if self.file_path.exists():
            self.load()

    def load(self) -> None:
        try:
            with self.file_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.state = ProgressState.from_json(data)
            LOGGER.info(
                "Loaded progress: page=%s card=%s processed_urls=%s",
                self.state.page_index,
                self.state.card_index,
                len(self.state.processed_urls or []),
            )
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Failed to load progress, starting fresh: %s", exc)
            self.state = ProgressState()

    def save(self) -> None:
        data = self.state.to_json()
        try:
            with self.file_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            LOGGER.debug(
                "Saved progress: page=%s card=%s processed_urls=%s",
                self.state.page_index,
                self.state.card_index,
                len(self.state.processed_urls or []),
            )
        except OSError as exc:
            LOGGER.error("Failed to write progress file %s: %s", self.file_path, exc)

    def update(self, page_index: Optional[int] = None, card_index: Optional[int] = None,
               processed_url: Optional[str] = None) -> None:
        if page_index is not None:
            self.state.page_index = page_index
        if card_index is not None:
            self.state.card_index = card_index
        if processed_url:
            urls = self.state.processed_urls or set()
            urls.add(processed_url)
            self.state.processed_urls = urls
        self.save()

    def mark_page_started(self, page_index: int) -> None:
        self.update(page_index=page_index, card_index=-1)

    def mark_card_processed(self, page_index: int, card_index: int, url: str) -> None:
        self.update(page_index=page_index, card_index=card_index, processed_url=url)

    def reset_card_index(self) -> None:
        self.state.card_index = -1
        self.save()
