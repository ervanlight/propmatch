"""
Pipeline scraping PropMatch.

Alur: scrape (best-effort) -> klasifikasi AI -> simpan (dedup) -> matching ->
generate dashboard -> kirim laporan Telegram.

Dijalankan MANUAL saja (tombol dashboard atau GitHub Actions "Run workflow")
-- lihat .github/workflows/scrape.yml. Lead dari landing page TIDAK lewat
sini lagi (api/submit-lead.py sekarang menulis langsung ke Turso, instan).
Setiap tahap dibungkus penanganan error supaya satu kegagalan tidak
menghentikan seluruh proses.
"""
import os
import time
import logging

import config
import store
from models import now_iso
from scraper import scrape_all
from classifier.claude_classifier import ClaudeClassifier
from matcher import engine
from matcher.claude_matcher import ClaudeMatcher
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

    # 2. Klasifikasi + simpan -- lewati panggilan AI untuk konten yang sudah
    # pernah diproses sebelumnya (mis. listing OLX yang sama masih tayang
    # beberapa hari berturut-turut). Ini penghematan biaya AI terbesar karena
    # listing sering muncul ulang di scraping harian tanpa perubahan isi.
    classifier = ClaudeClassifier()
    penjual_baru = 0
    pencari_baru = 0
    dilewati_sudah_pernah = 0
    for i, item in enumerate(raw_listings):
        h = store.raw_hash(item.get("source_url", ""), item.get("raw_text", ""))
        if store.has_seen_raw(h):
            dilewati_sudah_pernah += 1
            continue
        try:
            data = classifier.classify_property(
                item.get("raw_text", ""),
                item.get("source_url", ""),
                item.get("source_name", ""),
            )
            store.mark_seen_raw(h)  # tandai sudah diproses, apapun hasilnya
            result = store.save_listing(data)
            if result == "new":
                if data.get("status") == "JUAL":
                    penjual_baru += 1
                elif data.get("status") == "CARI":
                    pencari_baru += 1
        except Exception as e:
            logger.error("Gagal memproses satu listing: %s", e)

        if i < len(raw_listings) - 1 and config.CLAUDE_CALL_DELAY_SECONDS > 0:
            time.sleep(config.CLAUDE_CALL_DELAY_SECONDS)

    logger.info("Listing baru — Penjual: %d, Pencari: %d | Dilewati (sudah pernah): %d",
               penjual_baru, pencari_baru, dilewati_sudah_pernah)

    # 3. Matching deterministik + perkaya alasan dengan AI (opsional)
    top_matches = []
    try:
        top_matches = engine.find_matches(store.get_penjual(), store.get_pencari())
        if top_matches:
            ClaudeMatcher().enrich_reasons(top_matches, limit=5)
        match_result = store.save_matches(top_matches)
        logger.info("Matching selesai: %d pasangan di atas threshold (baru: %d, disegarkan: %d).",
                   len(top_matches), match_result["new"], match_result["refreshed"])
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
