"""
Migrasi satu-kali: pindahkan data lama dari data/*.json ke data/propmatch.db.

Jalankan sekali: python migrate_json_to_sqlite.py
Aman dijalankan berkali-kali (idempoten -- pakai INSERT OR IGNORE berbasis id).
File JSON lama TIDAK dihapus otomatis; backup manual dulu kalau mau hapus.
"""
import os
import json
import logging

import config
import db
from models import now_iso
from classifier.urgency import compute_urgency_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("migrate")


def _load(filename):
    path = os.path.join(config.DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Gagal baca %s: %s", filename, e)
        return []


def _guess_source(source_name: str) -> str:
    s = (source_name or "").lower()
    if "olx" in s:
        return "olx"
    if "threads" in s:
        return "threads"
    if "facebook" in s:
        return "facebook"
    if "telegram" in s:
        return "telegram_forward"
    return "telegram_forward"


def migrate_listings(items: list, table: str, conn) -> int:
    count = 0
    for it in items:
        urgency = compute_urgency_score(it.get("raw_text", ""))
        now = it.get("created_at") or now_iso()
        try:
            conn.execute(f"""
                INSERT OR IGNORE INTO {table}
                (id, lokasi, lokasi_display, harga, tipe_properti, lt_lb, kt_km, kontak,
                 urgensi, metode_bayar, kualitas_lead, urgency_score, catatan_ai, source_url,
                 source_name, source, raw_text, lead_status, created_at, updated_at,
                 deleted_at, last_confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)
            """, (
                it.get("id"), it.get("lokasi", ""), it.get("lokasi_display", ""),
                it.get("harga", 0), it.get("tipe_properti", ""), it.get("LT_LB", ""),
                it.get("KT_KM", ""), it.get("kontak", ""), it.get("urgensi", ""),
                it.get("metode_bayar", ""), it.get("kualitas_lead", ""), urgency,
                it.get("catatan_ai", ""), it.get("source_url", ""), it.get("source_name", ""),
                _guess_source(it.get("source_name", "")), it.get("raw_text", ""),
                it.get("created_at", now), it.get("updated_at", now), it.get("deleted_at"),
                it.get("updated_at", now),
            ))
            count += conn.execute("SELECT changes()").fetchone()[0]
        except Exception as e:
            logger.error("Gagal migrasi item %s: %s", it.get("id"), e)
    return count


def migrate_matches(matches: list, conn) -> int:
    count = 0
    now = now_iso()
    for m in matches:
        try:
            conn.execute("""
                INSERT INTO matches (seller_id, buyer_id, skor, skor_10, rincian, alasan,
                    alasan_ai, penjual_lokasi, penjual_harga, penjual_tipe, penjual_url,
                    penjual_kontak, pencari_lokasi, pencari_budget, pencari_url,
                    pencari_kontak, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m.get("penjual_id"), m.get("pencari_id"), m.get("skor"), m.get("skor_10"),
                json.dumps(m.get("rincian", {})), m.get("alasan", ""), m.get("alasan_ai", ""),
                m.get("penjual_lokasi"), m.get("penjual_harga"), m.get("penjual_tipe"),
                m.get("penjual_url"), m.get("penjual_kontak"), m.get("pencari_lokasi"),
                m.get("pencari_budget"), m.get("pencari_url"), m.get("pencari_kontak"), now,
            ))
            count += 1
        except Exception as e:
            logger.error("Gagal migrasi match: %s", e)
    return count


def main():
    conn = db.get_connection()

    penjual = _load("penjual.json")
    pencari = _load("pencari.json")
    matches = _load("match.json")
    seen_raw = _load("seen_raw.json")

    n_sellers = migrate_listings(penjual, "sellers", conn)
    conn.commit()
    n_buyers = migrate_listings(pencari, "buyers", conn)
    conn.commit()

    existing_matches = conn.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"]
    n_matches = migrate_matches(matches, conn) if existing_matches == 0 else 0
    conn.commit()

    n_seen = 0
    if isinstance(seen_raw, list):
        for h in seen_raw:
            conn.execute("INSERT OR IGNORE INTO seen_raw (hash, created_at) VALUES (?, ?)",
                        (h, now_iso()))
            n_seen += 1
    conn.commit()
    conn.close()

    logger.info("Migrasi selesai: %d penjual, %d pencari, %d match, %d hash seen_raw",
               n_sellers, n_buyers, n_matches, n_seen)
    logger.info("Database: %s", db.DB_PATH)
    logger.info("File JSON lama TIDAK dihapus -- backup manual dulu sebelum hapus jika perlu.")


if __name__ == "__main__":
    main()
