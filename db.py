"""
Lapisan koneksi & skema SQLite untuk PropMatch.

Menggantikan data/*.json. Database tunggal di data/propmatch.db, dipakai
bersama oleh bot.py (polling, proses panjang) dan main.py (cron harian) --
keduanya berjalan bergantian, bukan benar-benar bersamaan, jadi mode WAL
SQLite standar sudah cukup aman tanpa perlu infrastruktur locking tambahan.
"""
import os
import sqlite3
import logging

import config

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(config.DATA_DIR, "propmatch.db")

# Kolom inti yang sama untuk sellers & buyers (selain 'harga' yang berarti
# "harga jual" di sellers dan "budget" di buyers -- nama kolom disamakan
# supaya kode matcher/dashboard tidak perlu cabang logic per tabel).
_LISTING_COLUMNS = """
    id TEXT PRIMARY KEY,
    lokasi TEXT,
    lokasi_display TEXT,
    harga INTEGER DEFAULT 0,
    tipe_properti TEXT,
    lt_lb TEXT,
    kt_km TEXT,
    kontak TEXT,
    urgensi TEXT,
    metode_bayar TEXT,
    kualitas_lead TEXT,
    urgency_score INTEGER DEFAULT 0,
    catatan_ai TEXT,
    source_url TEXT,
    source_name TEXT,
    source TEXT CHECK(source IN ('olx','threads','facebook','telegram_forward','landing_page')) DEFAULT 'telegram_forward',
    raw_text TEXT,
    lead_status TEXT CHECK(lead_status IN ('new','contacted','negotiating','closed','lost')) DEFAULT 'new',
    created_at TEXT,
    updated_at TEXT,
    deleted_at TEXT,
    last_confirmed_at TEXT
"""

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sellers ({_LISTING_COLUMNS});
CREATE TABLE IF NOT EXISTS buyers ({_LISTING_COLUMNS});

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT,
    buyer_id TEXT,
    skor INTEGER,
    skor_10 REAL,
    urgency_score INTEGER DEFAULT 0,
    combined_score REAL,
    rincian TEXT,
    alasan TEXT,
    alasan_ai TEXT,
    penjual_lokasi TEXT,
    penjual_harga INTEGER,
    penjual_tipe TEXT,
    penjual_url TEXT,
    penjual_kontak TEXT,
    pencari_lokasi TEXT,
    pencari_budget INTEGER,
    pencari_url TEXT,
    pencari_kontak TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS seen_raw (
    hash TEXT PRIMARY KEY,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sellers_deleted ON sellers(deleted_at);
CREATE INDEX IF NOT EXISTS idx_buyers_deleted ON buyers(deleted_at);
CREATE INDEX IF NOT EXISTS idx_sellers_lead_status ON sellers(lead_status);
CREATE INDEX IF NOT EXISTS idx_buyers_lead_status ON buyers(lead_status);
"""

_initialized = False


def get_connection() -> sqlite3.Connection:
    """Buka koneksi baru dengan mode WAL (aman untuk akses bergantian dari
    proses berbeda: bot.py, main.py, script migrasi)."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _initialized
    if _initialized:
        return
    conn.executescript(SCHEMA)
    conn.commit()
    _initialized = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    c = get_connection()
    print("Database siap di:", DB_PATH)
    for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        print(" -", row["name"])
    c.close()
