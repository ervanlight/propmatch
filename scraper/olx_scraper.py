"""
Scraper OLX (best-effort) — terutama sisi PENJUAL, plus pencarian kata "dicari".

OLX memakai proteksi anti-bot kuat & rendering JavaScript, jadi scraping sering
gagal/timeout. Modul ini mencoba API internal OLX (JSON) lalu HTML sebagai
cadangan, dengan retry & timeout aman, dan tidak pernah crash (lewat BaseScraper).
"""
import logging
import time

import requests
from bs4 import BeautifulSoup

import config
from scraper.base import BaseScraper

logger = logging.getLogger(__name__)

OLX_LOCATIONS = {"surabaya": "4000202", "sidoarjo": "4000204"}
OLX_PROPERTY_CATEGORY = "5000001"


class OLXScraper(BaseScraper):
    name = "OLX"
    buyer_focused = False

    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/html,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def fetch(self, limit: int) -> list:
        results = []
        per_loc = max(5, limit // max(1, len(OLX_LOCATIONS)))
        for city, loc_id in OLX_LOCATIONS.items():
            results.extend(self._scrape_location(loc_id, per_loc, city))
            time.sleep(1.5)

        if not results and config.USE_MOCK_DATA:
            logger.info("USE_MOCK_DATA=1 -> memakai data contoh OLX.")
            return self._mock_data()
        return results

    def _try_api(self, location_id: str, size: int):
        url = (f"https://www.olx.co.id/api/relevance/v4/search?category={OLX_PROPERTY_CATEGORY}"
               f"&location={location_id}&location_facet_limit=20&platform=web-desktop&size={size}")
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        out = []
        for ad in resp.json().get("data", [])[:size]:
            title = ad.get("title", "")
            price = (ad.get("price") or {}).get("value", {}).get("display", "")
            loc = ", ".join(filter(None, [
                (ad.get("locations_resolved") or {}).get("ADMIN_LEVEL_3_name"),
                (ad.get("locations_resolved") or {}).get("ADMIN_LEVEL_2_name"),
            ]))
            desc = (ad.get("description") or "")[:400]
            ad_id = ad.get("id")
            out.append({
                "raw_text": f"Judul: {title}\nHarga: {price}\nLokasi: {loc}\nDeskripsi: {desc}",
                "source_url": f"https://www.olx.co.id/item/{ad_id}" if ad_id else "",
                "source_name": "OLX",
            })
        return out

    def _try_html(self, limit: int):
        url = f"https://www.olx.co.id/properti_c{OLX_PROPERTY_CATEGORY}"
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        out = []
        for item in soup.find_all("li", {"data-aut-id": "itemBox"})[:limit]:
            title_elem = item.find("span", {"data-aut-id": "itemTitle"})
            price_elem = item.find("span", {"data-aut-id": "itemPrice"})
            loc_elem = item.find("span", {"data-aut-id": "item-location"})
            link = item.find("a")
            if not (title_elem and link):
                continue
            href = link.get("href", "")
            full_url = f"https://www.olx.co.id{href}" if href.startswith("/") else href
            out.append({
                "raw_text": (f"Judul: {title_elem.text.strip()}\n"
                             f"Harga: {price_elem.text.strip() if price_elem else ''}\n"
                             f"Lokasi: {loc_elem.text.strip() if loc_elem else ''}"),
                "source_url": full_url,
                "source_name": "OLX",
            })
        return out

    def _scrape_location(self, loc_id: str, limit: int, city: str) -> list:
        for attempt in range(2):
            try:
                data = self._try_api(loc_id, limit)
                if data:
                    logger.info("OLX API %s: %d listing", city, len(data))
                    return data
            except Exception as e:
                logger.warning("OLX API %s gagal (%d): %s", city, attempt + 1, e)
            try:
                data = self._try_html(limit)
                if data:
                    logger.info("OLX HTML %s: %d listing", city, len(data))
                    return data
            except Exception as e:
                logger.warning("OLX HTML %s gagal (%d): %s", city, attempt + 1, e)
            time.sleep(2)
        return []

    @staticmethod
    def _mock_data():
        return [
            {"raw_text": ("Dijual Cepat Rumah Minimalis Waru Sidoarjo. Harga 650 Juta. Nego. "
                          "LT 90 LB 70. 3 Kamar Tidur. Bisa KPR. WA 081234567890."),
             "source_url": "https://www.olx.co.id/item/rumah-waru-mock-1", "source_name": "OLX (Mock)"},
        ]
