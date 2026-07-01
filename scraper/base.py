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
import re

import config

logger = logging.getLogger(__name__)


def _kw_in_text(keyword: str, text: str) -> bool:
    """Cocokkan kata kunci dengan batas kata untuk kata tunggal (hindari
    'max ' nyangkut di 'maximus', 'candi' di 'candid'); frasa multi-kata
    dicocokkan apa adanya."""
    keyword = keyword.strip()
    if not keyword:
        return False
    if " " in keyword:
        return keyword in text
    return re.search(r"\b" + re.escape(keyword) + r"\b", text) is not None


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
        """Sinyal NIAT BELI (demand-side) -- aset paling bernilai."""
        t = (text or "").lower()
        return any(_kw_in_text(kw, t) for kw in config.BUYER_KEYWORDS)

    @staticmethod
    def looks_like_property(text: str) -> bool:
        """Apakah teks ini benar-benar soal PROPERTI (jual atau cari)? Dipakai
        sebagai filter pra-AI: banyak postingan medsos menyebut nama wilayah
        tapi bukan soal properti sama sekali. Tanpa ini, sampah non-properti
        ikut terklasifikasi & mencemari database (dan memboroskan kuota AI)."""
        t = (text or "").lower()
        return any(_kw_in_text(kw, t) for kw in config.PROPERTY_KEYWORDS)

    @staticmethod
    def is_relevant_region(text: str) -> bool:
        t = (text or "").lower()
        return any(_kw_in_text(region, t) for region in config.TARGET_REGIONS)
