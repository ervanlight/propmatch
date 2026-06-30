"""
Kerangka dasar scraper multi-sumber.

Setiap sumber (OLX, Threads, Facebook, dst) mewarisi BaseScraper dan
mengimplementasikan `fetch()` yang mengembalikan list item mentah berbentuk:
    {"raw_text": str, "source_url": str, "source_name": str}

BaseScraper menyediakan utilitas bersama: deteksi sinyal niat-beli (demand-side),
filter relevansi wilayah, dan pembungkus aman supaya satu sumber yang error tidak
menjatuhkan sumber lain.
"""
import logging

import config

logger = logging.getLogger(__name__)


class BaseScraper:
    name = "base"
    # Apakah sumber ini terutama menangkap PEMBELI (demand-side)?
    buyer_focused = False

    def fetch(self, limit: int) -> list:
        """Implementasikan di subclass. Harus mengembalikan list item mentah."""
        raise NotImplementedError

    def scrape(self, limit: int = None) -> list:
        """Pembungkus aman: tidak pernah melempar exception keluar."""
        limit = limit or config.SCRAPER_LIMIT
        try:
            items = self.fetch(limit) or []
            for it in items:
                it.setdefault("source_name", self.name)
            logger.info("[%s] mengembalikan %d item.", self.name, len(items))
            return items
        except Exception as e:
            logger.warning("[%s] gagal: %s", self.name, e)
            return []

    # ----- utilitas bersama -------------------------------------------------
    @staticmethod
    def looks_like_buyer(text: str) -> bool:
        t = (text or "").lower()
        return any(kw in t for kw in config.BUYER_KEYWORDS)

    @staticmethod
    def is_relevant_region(text: str) -> bool:
        t = (text or "").lower()
        return any(region in t for region in config.TARGET_REGIONS)
