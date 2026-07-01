"""
Scraper Threads (Meta) — fokus menangkap NIAT BELI (demand-side), PUBLIK.

Berbeda dengan Facebook Group (yang butuh sesi login pribadi & berisi data
personal anggota tertutup), pencarian Threads bersifat PUBLIK — siapa pun bisa
membukanya tanpa login, persis seperti mencari di Twitter/X. Karena itu
otomasi di sini tidak punya masalah privasi yang sama; ini setara dengan
scraping OLX (membaca konten publik).

Catatan teknis penting: hasil pencarian Threads dirender penuh lewat
JavaScript — permintaan HTTP biasa (requests) hanya mendapat kerangka kosong.
Modul ini memakai Playwright (headless Chromium) untuk benar-benar merender
halaman lalu mengekstrak teks tiap postingan dari DOM.

Kata kunci PENDEK (2-3 kata, mis. "rumah sidoarjo") terbukti jauh lebih efektif
daripada frasa panjang & spesifik (mis. "dicari rumah waru sidoarjo" sering
"No results"), karena index pencarian Threads berbasis kemiripan luas.
"""
import logging
import time

import config
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.threads.net/search?q={query}&serp_type=default"

_EXTRACT_JS = """() => {
    const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
    const seen = new Set();
    const out = [];
    for (const a of links) {
        const container = a.closest('div[data-pressable-container]');
        if (!container) continue;
        const text = container.innerText || '';
        const href = a.href.split('?')[0];
        if (seen.has(href) || text.length < 20) continue;
        seen.add(href);
        out.push({text, url: href});
    }
    return out;
}"""


class ThreadsScraper(BaseScraper):
    name = "Threads"
    buyer_focused = True

    def fetch(self, limit: int) -> list:
        try:
            return self._fetch_with_playwright(limit)
        except ImportError:
            logger.warning("Playwright belum terpasang. Jalankan: pip install playwright "
                          "&& python -m playwright install chromium")
        except Exception as e:
            logger.warning("Threads scraping gagal: %s", e)

        if config.USE_MOCK_DATA:
            return self._mock_data()
        return []

    def _fetch_with_playwright(self, limit: int) -> list:
        from playwright.sync_api import sync_playwright

        results = []
        seen_urls = set()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            )
            try:
                for keyword in config.THREADS_KEYWORDS:
                    if len(results) >= limit:
                        break
                    try:
                        posts = self._search_keyword(page, keyword)
                    except Exception as e:
                        logger.warning("Threads pencarian '%s' gagal: %s", keyword, e)
                        continue
                    for text, url in posts:
                        if url in seen_urls:
                            continue
                        # Dua saringan wajib SEBELUM kirim ke AI: (1) menyebut
                        # wilayah target, DAN (2) benar-benar soal properti.
                        # Memangkas sampah non-properti di sumbernya (hemat kuota
                        # AI + jaga database tetap bersih).
                        if not self.is_relevant_region(text):
                            continue
                        if not self.looks_like_property(text):
                            continue
                        seen_urls.add(url)
                        results.append({
                            "raw_text": text[:600],
                            "source_url": url,
                            "source_name": "Threads",
                        })
                        if len(results) >= limit:
                            break
                    time.sleep(1)
            finally:
                browser.close()
        logger.info("Threads: %d postingan relevan terkumpul dari %d kata kunci.",
                    len(results), len(config.THREADS_KEYWORDS))
        return results

    def _search_keyword(self, page, keyword: str):
        url = SEARCH_URL.format(query=keyword.replace(" ", "%20"))
        page.goto(url, timeout=30000)
        page.wait_for_timeout(2500)
        items = page.evaluate(_EXTRACT_JS)
        out = []
        for item in items:
            text = item.get("text", "").strip()
            url_ = item.get("url", "")
            if not text or "No results" in text:
                continue
            out.append((text, url_))
        return out

    @staticmethod
    def _mock_data():
        return [
            {"raw_text": ("Dicari rumah daerah Rungkut atau Gunung Anyar Surabaya budget 700jt, "
                          "siap KPR untuk keluarga muda. Info dong sespp."),
             "source_url": "https://www.threads.net/@mock/post/1", "source_name": "Threads (Mock)"},
        ]
