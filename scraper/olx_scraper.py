"""
Scraper OLX (best-effort).

OLX memakai proteksi anti-bot yang kuat dan rendering JavaScript, jadi scraping
sederhana sering gagal/timeout. Modul ini:
  - mencoba endpoint API internal OLX (JSON) lebih dulu, lalu HTML sebagai cadangan;
  - melakukan retry dengan timeout aman;
  - TIDAK pernah melempar exception keluar (mengembalikan list, bisa kosong);
  - hanya mengeluarkan data mock kalau USE_MOCK_DATA=1 (khusus testing lokal),
    supaya data palsu tidak mencemari database broker di produksi.
"""
import logging
import time

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

# Kode lokasi OLX: Surabaya & Sidoarjo (region Jawa Timur).
OLX_LOCATIONS = {
    "surabaya": "4000202",
    "sidoarjo": "4000204",
}
OLX_PROPERTY_CATEGORY = "5000001"  # kategori properti


class OLXScraper:
    name = "OLX"

    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/html,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _try_api(self, location_id: str, size: int):
        url = (f"https://www.olx.co.id/api/relevance/v4/search?category={OLX_PROPERTY_CATEGORY}"
               f"&location={location_id}&location_facet_limit=20&platform=web-desktop&size={size}")
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        out = []
        for ad in payload.get("data", [])[:size]:
            title = ad.get("title", "")
            price = (ad.get("price") or {}).get("value", {}).get("display", "")
            loc = ", ".join(filter(None, [
                (ad.get("locations_resolved") or {}).get("ADMIN_LEVEL_3_name"),
                (ad.get("locations_resolved") or {}).get("ADMIN_LEVEL_2_name"),
            ]))
            desc = (ad.get("description") or "")[:400]
            ad_id = ad.get("id")
            full_url = f"https://www.olx.co.id/item/{ad_id}" if ad_id else ""
            out.append({
                "raw_text": f"Judul: {title}\nHarga: {price}\nLokasi: {loc}\nDeskripsi: {desc}",
                "source_url": full_url,
                "source_name": "OLX",
            })
        return out

    def _try_html(self, location_id: str, limit: int):
        url = f"https://www.olx.co.id/properti_c{OLX_PROPERTY_CATEGORY}"
        resp = requests.get(url, headers=self.headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.find_all("li", {"data-aut-id": "itemBox"})
        out = []
        for item in items[:limit]:
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

    def scrape(self, limit: int = 20) -> list:
        results = []
        per_loc = max(5, limit // max(1, len(OLX_LOCATIONS)))
        for city, loc_id in OLX_LOCATIONS.items():
            got = self._scrape_location(loc_id, per_loc, city)
            results.extend(got)
            time.sleep(1.5)  # jeda sopan antar request

        if not results:
            logger.warning("OLX tidak mengembalikan data (kemungkinan diblokir/timeout).")
            if config.USE_MOCK_DATA:
                logger.info("USE_MOCK_DATA=1 -> memakai data contoh untuk testing.")
                return self._mock_data()
        return results

    def _scrape_location(self, loc_id: str, limit: int, city: str) -> list:
        for attempt in range(2):
            try:
                data = self._try_api(loc_id, limit)
                if data:
                    logger.info("OLX API %s: %d listing", city, len(data))
                    return data
            except Exception as e:
                logger.warning("OLX API %s gagal (percobaan %d): %s", city, attempt + 1, e)
            try:
                data = self._try_html(loc_id, limit)
                if data:
                    logger.info("OLX HTML %s: %d listing", city, len(data))
                    return data
            except Exception as e:
                logger.warning("OLX HTML %s gagal (percobaan %d): %s", city, attempt + 1, e)
            time.sleep(2)
        return []

    # Kompatibilitas dengan nama lama yang dipakai main.py sebelumnya.
    def scrape_sidoarjo_surabaya(self, limit: int = 20) -> list:
        return self.scrape(limit)

    @staticmethod
    def _mock_data():
        return [
            {
                "raw_text": ("Dijual Cepat Rumah Minimalis Waru Sidoarjo. Harga 650 Juta. Nego. "
                             "LT 90 LB 70. 3 Kamar Tidur. Bisa KPR. WA 081234567890."),
                "source_url": "https://www.olx.co.id/item/rumah-waru-mock-1",
                "source_name": "OLX (Mock)",
            },
            {
                "raw_text": ("Dicari rumah daerah Rungkut atau Gunung Anyar Surabaya. Budget 700jt. "
                             "Siap KPR. Untuk keluarga muda. Hub 0858111222."),
                "source_url": "https://www.facebook.com/groups/mock-cari-1",
                "source_name": "Facebook (Mock)",
            },
            {
                "raw_text": ("Dicari ruko Sidoarjo kota atau Gedangan untuk usaha kuliner. "
                             "Budget sewa 50jt/tahun. Butuh cepat."),
                "source_url": "https://www.facebook.com/groups/mock-cari-2",
                "source_name": "Facebook (Mock)",
            },
        ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(OLXScraper().scrape(limit=5))
