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

# Watchdog: kalau sumber ini menghasilkan 0 listing N run berturut-turut,
# kemungkinan besar diblokir/berubah struktur -- tanpa ini, Harvey baru sadar
# scraper mati kalau kebetulan iseng cek, bukan diberi tahu aktif. Facebook
# DIKECUALIKAN karena 0 itu memang selalu diharapkan (stub disengaja, lihat
# scraper/facebook_scraper.py).
WATCHDOG_STREAK_THRESHOLD = 2
WATCHDOG_EXCLUDE = {"Facebook"}


def _check_scraper_watchdog(per_source: dict) -> None:
    meta = store.get_meta()
    alerts = []
    updates = {}
    for name, count in per_source.items():
        if name in WATCHDOG_EXCLUDE:
            continue
        key = f"scraper_zero_streak_{name}"
        streak = int(meta.get(key, 0) or 0)
        if count == 0:
            streak += 1
        else:
            streak = 0
        if streak >= WATCHDOG_STREAK_THRESHOLD:
            alerts.append((name, streak))
            streak = 0  # reset supaya tidak alert tiap run selama masih 0 -- alert ulang tiap kelipatan threshold
        updates[key] = streak

    if updates:
        store.save_meta(updates)

    if alerts:
        lines = [f"⚠️ <b>Scraper mungkin bermasalah</b>"]
        for name, streak in alerts:
            lines.append(f"• <b>{name}</b>: 0 listing selama {streak} run scraping berturut-turut. "
                        f"Kemungkinan diblokir atau struktur halaman berubah, cek manual.")
        try:
            TelegramNotifier().send_message("\n".join(lines))
        except Exception as e:
            logger.error("Gagal kirim alert watchdog: %s", e)


def run():
    logger.info("=== Memulai pipeline harian PropMatch ===")

    # 1. Scraping multi-sumber (OLX, Threads, Facebook) — best-effort, aman
    raw_listings, per_source = scrape_all()
    logger.info("Listing mentah terkumpul: %d dari sumber %s", len(raw_listings), per_source)
    try:
        _check_scraper_watchdog(per_source)
    except Exception as e:
        logger.error("Watchdog scraper gagal jalan: %s", e)

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

    # 4b. Sinkronkan arsip Google Sheets (best-effort -- dilewati kalau belum
    # dikonfigurasi, tidak pernah menggagalkan pipeline utama).
    if config.GOOGLE_SHEETS_ID:
        try:
            from integrations.google_sheets import sync_all
            sync_all()
        except Exception as e:
            logger.error("Gagal sinkronisasi Google Sheets: %s", e)

    # 5. Laporan Telegram
    try:
        report = build_daily_report(s, penjual_baru, pencari_baru, top_matches, DASHBOARD_URL)
        TelegramNotifier().send_message(report)
    except Exception as e:
        logger.error("Gagal kirim laporan Telegram: %s", e)

    logger.info("=== Pipeline selesai ===")


if __name__ == "__main__":
    run()
