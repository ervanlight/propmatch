"""
Sumber Facebook Group — DENGAN SENGAJA tidak diotomasi sebagai scraper massal.

Kenapa: mengekstrak cookie sesi Facebook dan melakukan scraping otomatis atas
isi grup (apalagi data kontak pribadi anggota) tanpa sepengetahuan mereka
melewati batas privasi yang wajar, meskipun Harvey sendiri anggota grup
tersebut. Membaca grup sebagai manusia itu wajar; mengotomasi ekstraksi massal
& menyimpannya permanen ke database komersial adalah hal berbeda.

Jalur yang dipakai sebagai gantinya: Harvey membaca grup secara manual, lalu
forward/paste postingan yang menarik ke bot Telegram (lihat delivery/handler.py).
Ini tetap cepat (hitungan detik per listing) dan sepenuhnya berada di bawah
kendali & pertimbangan manusia.

Kelas ini disisakan sebagai stub no-op supaya config.ENABLED_SCRAPERS="facebook"
tidak error, dan supaya niat desainnya terdokumentasi untuk sesi berikutnya.
"""
import logging

from scraper.base import BaseScraper

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    name = "Facebook"
    buyer_focused = True

    def fetch(self, limit: int) -> list:
        logger.info(
            "Facebook scraper otomatis dinonaktifkan dengan sengaja (privasi). "
            "Gunakan forward manual ke bot Telegram untuk listing dari grup Facebook."
        )
        return []
