"""
Pipeline harian PropMatch.

Alur: scrape (best-effort) -> klasifikasi AI -> simpan (dedup) -> matching ->
generate dashboard -> kirim laporan Telegram.

Dijalankan terjadwal tiap pagi (GitHub Actions / cron). Setiap tahap dibungkus
penanganan error supaya satu kegagalan tidak menghentikan seluruh proses.
"""
import os
import time
import logging

import config
import store
from models import now_iso
from scraper import scrape_all
from classifier.gemini_classifier import GeminiClassifier
from matcher import engine
from matcher.gemini_matcher import GeminiMatcher
from delivery.telegram_bot import TelegramNotifier, build_daily_report
from dashboard.generator import generate_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "")


def run():
    logger.info("=== Memulai pipeline harian PropMatch ===")

    # 1. Scraping multi-sumber (OLX, Threads, Facebook) — best-effort, aman
    raw_listings, per_source = scrape_all()
    logger.info("Listing mentah terkumpul: %d dari sumber %s", len(raw_listings), per_source)

    # 2. Klasifikasi + simpan — diberi jeda antar panggilan supaya tidak
    # menabrak batas permintaan-per-menit Gemini (lihat config.GEMINI_CALL_DELAY_SECONDS)
    classifier = GeminiClassifier()
    penjual_baru = pencari_baru = 0
    for i, item in enumerate(raw_listings):
        try:
            data = classifier.classify_property(
                item.get("raw_text", ""),
                item.get("source_url", ""),
                item.get("source_name", ""),
            )
            result = store.save_listing(data)
            if result == "new":
                if data.get("status") == "JUAL":
                    penjual_baru += 1
                elif data.get("status") == "CARI":
                    pencari_baru += 1
        except Exception as e:
            logger.error("Gagal memproses satu listing: %s", e)

        if i < len(raw_listings) - 1 and not GeminiClassifier._daily_quota_exhausted:
            time.sleep(config.GEMINI_CALL_DELAY_SECONDS)

    logger.info("Listing baru — Penjual: %d, Pencari: %d", penjual_baru, pencari_baru)

    # 3. Matching deterministik + perkaya alasan dengan AI (opsional)
    top_matches = []
    try:
        top_matches = engine.find_matches(store.get_penjual(), store.get_pencari())
        if top_matches:
            GeminiMatcher().enrich_reasons(top_matches, limit=5)
        store.save_matches(top_matches)
        logger.info("Matching selesai: %d pasangan di atas threshold.", len(top_matches))
    except Exception as e:
        logger.error("Matching gagal: %s", e)

    # 4. Simpan metadata & generate dashboard
    s = store.stats()
    store.save_meta({"last_run": now_iso(), **s})
    try:
        generate_dashboard()
    except Exception as e:
        logger.error("Gagal generate dashboard: %s", e)

    # 5. Laporan Telegram
    try:
        report = build_daily_report(s, penjual_baru, pencari_baru, top_matches, DASHBOARD_URL)
        TelegramNotifier().send_message(report)
    except Exception as e:
        logger.error("Gagal kirim laporan Telegram: %s", e)

    logger.info("=== Pipeline selesai ===")


if __name__ == "__main__":
    run()
