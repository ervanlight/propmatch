"""
Lapisan koneksi & skema database -- Turso (libSQL remote).

Kenapa pindah dari file SQLite lokal ke Turso: dashboard live (Vercel) dan
GitHub Actions (eksekusi scraping) perlu menulis & membaca database YANG SAMA
dari internet, sedangkan file SQLite lokal tidak bisa diakses dari luar
laptop. Turso = SQLite yang di-hosting, dialek SQL nyaris identik sehingga
seluruh query yang sudah ada (store.py) tetap jalan tanpa banyak perubahan.

Satu-satunya sumber kebenaran sekarang: Turso. bot.py, main.py (lokal/GitHub
Actions), dan semua serverless function di api/ membaca & menulis ke sini.
"""
import os
import logging

import libsql_client

import config

logger = logging.getLogger(__name__)

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

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

# Setiap statement terpisah (libsql tidak punya executescript multi-statement
# seperti sqlite3 stdlib -- dieksekusi satu per satu lewat _ensure_schema).
SCHEMA_STATEMENTS = [
    f"CREATE TABLE IF NOT EXISTS sellers ({_LISTING_COLUMNS})",
    f"CREATE TABLE IF NOT EXISTS buyers ({_LISTING_COLUMNS})",
    """
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
        penjual_catatan TEXT,
        pencari_lokasi TEXT,
        pencari_budget INTEGER,
        pencari_url TEXT,
        pencari_kontak TEXT,
        pencari_catatan TEXT,
        -- Status pasangan match ITU SENDIRI (beda dari lead_status milik
        -- penjual/pencari): 'potential' = masih dihitung ulang otomatis tiap
        -- matching jalan, 'contacted'/'negotiating' = sedang Harvey follow-up
        -- (dibekukan, tidak diutak-atik lagi oleh mesin matching), 'closed'/
        -- 'lost' = sudah selesai (dibekukan permanen, jadi histori).
        status TEXT CHECK(status IN ('potential','contacted','negotiating','closed','lost')) DEFAULT 'potential',
        created_at TEXT,
        updated_at TEXT,
        UNIQUE(seller_id, buyer_id)
    )
    """,
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)",
    "CREATE TABLE IF NOT EXISTS seen_raw (hash TEXT PRIMARY KEY, created_at TEXT)",
    # Migrasi kolom baru untuk tabel matches yang sudah ada di Turso (CREATE
    # TABLE IF NOT EXISTS di atas tidak menambah kolom ke tabel lama) --
    # menampilkan "apa yang diminta penjual/pencari", bukan cuma lokasi+harga.
    # Turso TIDAK mendukung "ADD COLUMN IF NOT EXISTS" (lihat _ensure_schema:
    # statement ALTER TABLE ditangani idempotent lewat try/except di sana).
    "ALTER TABLE matches ADD COLUMN penjual_catatan TEXT",
    "ALTER TABLE matches ADD COLUMN pencari_catatan TEXT",
    "CREATE INDEX IF NOT EXISTS idx_sellers_deleted ON sellers(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_buyers_deleted ON buyers(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_sellers_lead_status ON sellers(lead_status)",
    "CREATE INDEX IF NOT EXISTS idx_buyers_lead_status ON buyers(lead_status)",
    "CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status)",
]

_initialized = False


def get_connection() -> libsql_client.ClientSync:
    """Buka client Turso baru. Dipanggil sekali per request/run (bukan
    long-lived) -- cocok untuk pola serverless maupun script pendek."""
    if not TURSO_DATABASE_URL:
        raise RuntimeError(
            "TURSO_DATABASE_URL belum diset. Isi di .env (lokal) atau "
            "environment variable Vercel/GitHub Actions Secrets."
        )
    client = libsql_client.create_client_sync(
        url=TURSO_DATABASE_URL,
        auth_token=TURSO_AUTH_TOKEN,
    )
    _ensure_schema(client)
    return client


def _ensure_schema(client: libsql_client.ClientSync) -> None:
    global _initialized
    if _initialized:
        return
    for stmt in SCHEMA_STATEMENTS:
        try:
            client.execute(stmt)
        except Exception:
            # ALTER TABLE ADD COLUMN tidak idempotent di Turso (tidak dukung
            # "IF NOT EXISTS") -- begitu kolom sudah ada, statement ini akan
            # selalu gagal di cold-start berikutnya. Aman diabaikan HANYA
            # untuk ALTER TABLE; error lain (CREATE TABLE/INDEX) tetap dilempar.
            if stmt.strip().upper().startswith("ALTER TABLE"):
                continue
            raise
    _initialized = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    c = get_connection()
    print("Terhubung ke Turso:", TURSO_DATABASE_URL)
    res = c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for row in res.rows:
        print(" -", row["name"])
    c.close()
