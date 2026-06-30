"""
Scraper Threads (Meta) — fokus menangkap NIAT BELI (demand-side).

Strategi: untuk tiap kata kunci di config.THREADS_KEYWORDS (mis. "dicari rumah
sidoarjo"), buka halaman pencarian publik Threads lalu ekstrak teks postingan
dari blob JSON yang tertanam di HTML. Hasil disaring agar relevan wilayah &
mengandung sinyal niat beli.

Catatan jujur: Threads tidak punya API pencarian publik resmi dan memakai
rendering JavaScript + token internal, jadi pendekatan ini BEST-EFFORT — bisa
berubah/diblokir sewaktu-waktu. BaseScraper memastikan kegagalan tidak
menjatuhkan pipeline. Untuk hasil stabil, andalkan forward manual ke bot +
scraper Facebook (sesi login).
"""
import re
import json
import logging
import time

import requests

import config
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class ThreadsScraper(BaseScraper):
    name = "Threads"
    buyer_focused = True

    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            # App ID web Instagram/Threads; sering diperlukan untuk endpoint publik.
            "X-IG-App-ID": "238260118697367",
        }

    def fetch(self, limit: int) -> list:
        results = []
        seen = set()
        for kw in config.THREADS_KEYWORDS:
            try:
                posts = self._search(kw)
            except Exception as e:
                logger.warning("Threads pencarian '%s' gagal: %s", kw, e)
                posts = []
            for text, url in posts:
                key = text[:120]
                if key in seen:
                    continue
                seen.add(key)
                if not self.is_relevant_region(text):
                    continue
                results.append({
                    "raw_text": text,
                    "source_url": url,
                    "source_name": "Threads",
                })
                if len(results) >= limit:
                    break
            time.sleep(1.5)
            if len(results) >= limit:
                break

        if not results and config.USE_MOCK_DATA:
            return self._mock_data()
        return results

    def _search(self, keyword: str):
        url = f"https://www.threads.net/search?q={requests.utils.quote(keyword)}&serp_type=default"
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        return self._extract_posts(resp.text)

    @staticmethod
    def _extract_posts(html: str):
        """Ambil caption postingan dari blob JSON yang tertanam di halaman."""
        posts = []
        # Threads menaruh data di banyak script JSON; cari field 'caption.text'
        # dan 'code' (shortcode permalink) secara longgar.
        for m in re.finditer(r'"caption"\s*:\s*\{[^}]*?"text"\s*:\s*"([^"]{15,})"', html):
            text = bytes(m.group(1), "utf-8").decode("unicode_escape", errors="ignore")
            posts.append((text.strip(), "https://www.threads.net/"))
        # Fallback: ambil pasangan code + text terpisah bila pola di atas tak kena.
        if not posts:
            for m in re.finditer(r'"text"\s*:\s*"([^"]{25,})"', html):
                text = bytes(m.group(1), "utf-8").decode("unicode_escape", errors="ignore")
                posts.append((text.strip(), "https://www.threads.net/"))
        return posts[:50]

    @staticmethod
    def _mock_data():
        return [
            {"raw_text": ("Dicari rumah daerah Rungkut atau Gunung Anyar Surabaya budget 700jt, "
                          "siap KPR untuk keluarga muda. Info dong sespp."),
             "source_url": "https://www.threads.net/@mock/post/1", "source_name": "Threads (Mock)"},
            {"raw_text": ("Butuh ruko Sidoarjo kota / Gedangan buat usaha, budget sewa 50jt setahun, "
                          "minta info yang available."),
             "source_url": "https://www.threads.net/@mock/post/2", "source_name": "Threads (Mock)"},
        ]
