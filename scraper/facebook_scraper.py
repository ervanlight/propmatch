"""
Scraper Facebook Group — sumber PEMBELI (demand-side) paling kaya.

Di grup jual-beli properti, calon pembeli rutin menulis "dicari rumah ...",
"butuh ruko ...", lengkap dengan budget & lokasi. Ini aset paling bernilai
karena sisi penjual sudah melimpah di portal.

Cara kerja: memakai versi ringan mbasic.facebook.com (HTML murni, mudah
di-parse) dengan SESI LOGIN HARVEY SENDIRI (cookie) untuk membaca grup yang dia
ikuti. Tanpa FB_COOKIE & FB_GROUP_IDS, scraper ini otomatis dilewati.

Catatan: ini mengakses data yang memang sudah bisa Harvey lihat sebagai anggota
grup, untuk keperluan internal pribadi. Jaga kerahasiaan cookie (simpan sebagai
secret, jangan commit). Pendekatan mbasic bersifat best-effort dan bisa berubah
mengikuti perubahan Facebook.
"""
import re
import logging
import time

import requests
from bs4 import BeautifulSoup

import config
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    name = "Facebook"
    buyer_focused = True

    def __init__(self):
        self.cookie = config.FB_COOKIE
        self.group_ids = config.FB_GROUP_IDS
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "Cookie": self.cookie,
        }

    def fetch(self, limit: int) -> list:
        if not self.cookie or not self.group_ids:
            logger.info("Facebook dilewati: FB_COOKIE / FB_GROUP_IDS belum diset.")
            if config.USE_MOCK_DATA:
                return self._mock_data()
            return []

        results = []
        per_group = max(5, limit // max(1, len(self.group_ids)))
        for gid in self.group_ids:
            try:
                results.extend(self._scrape_group(gid, per_group))
            except Exception as e:
                logger.warning("Facebook grup %s gagal: %s", gid, e)
            time.sleep(2)
            if len(results) >= limit:
                break
        return results[:limit]

    def _scrape_group(self, group_id: str, limit: int) -> list:
        url = f"https://mbasic.facebook.com/groups/{group_id}"
        resp = requests.get(url, headers=self.headers, timeout=20, allow_redirects=True)
        if "login" in resp.url or resp.status_code != 200:
            raise RuntimeError("sesi tidak valid / diminta login (cek FB_COOKIE)")

        soup = BeautifulSoup(resp.text, "html.parser")
        out = []
        # Di mbasic, isi postingan umumnya berada di blok artikel/cerita.
        candidates = soup.find_all(["div", "article"], attrs={"data-ft": True})
        if not candidates:
            candidates = soup.find_all("div", id=re.compile(r"^u_"))

        for node in candidates:
            text = node.get_text(" ", strip=True)
            if not text or len(text) < 25:
                continue
            # Fokus PEMBELI: hanya ambil yang bersinyal niat beli & relevan wilayah.
            if not self.looks_like_buyer(text):
                continue
            if not self.is_relevant_region(text):
                continue
            link = node.find("a", href=re.compile(r"(story|permalink|/groups/)"))
            href = link.get("href") if link else ""
            full = f"https://mbasic.facebook.com{href}" if href.startswith("/") else href
            out.append({
                "raw_text": text[:600],
                "source_url": full or url,
                "source_name": "Facebook Group",
            })
            if len(out) >= limit:
                break
        logger.info("Facebook grup %s: %d postingan pembeli terjaring", group_id, len(out))
        return out

    @staticmethod
    def _mock_data():
        return [
            {"raw_text": ("Dicari rumah siap huni daerah Waru / Gedangan Sidoarjo, budget maksimal "
                          "680 juta, KPR bisa. Untuk keluarga. WA 0812-5566-7788"),
             "source_url": "https://facebook.com/groups/mock/posts/1",
             "source_name": "Facebook Group (Mock)"},
        ]
