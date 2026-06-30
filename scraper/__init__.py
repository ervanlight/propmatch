"""
Registry scraper multi-sumber.

main.py memanggil scrape_all() yang menjalankan semua scraper yang diaktifkan
lewat config.ENABLED_SCRAPERS, masing-masing dibungkus aman (BaseScraper.scrape).
"""
import logging

import config

logger = logging.getLogger(__name__)


def _build(name: str):
    name = name.lower()
    if name == "olx":
        from scraper.olx_scraper import OLXScraper
        return OLXScraper()
    if name == "threads":
        from scraper.threads_scraper import ThreadsScraper
        return ThreadsScraper()
    if name == "facebook":
        from scraper.facebook_scraper import FacebookScraper
        return FacebookScraper()
    logger.warning("Scraper tidak dikenal: %s", name)
    return None


def get_enabled_scrapers():
    scrapers = []
    for name in config.ENABLED_SCRAPERS:
        s = _build(name)
        if s:
            scrapers.append(s)
    return scrapers


def scrape_all(limit: int = None):
    """Jalankan semua scraper aktif, gabungkan hasilnya. Tidak pernah crash."""
    limit = limit or config.SCRAPER_LIMIT
    all_items = []
    per_source = {}
    for scraper in get_enabled_scrapers():
        items = scraper.scrape(limit)
        per_source[scraper.name] = len(items)
        all_items.extend(items)
    logger.info("Total item mentah dari semua sumber: %d %s", len(all_items), per_source)
    return all_items, per_source
