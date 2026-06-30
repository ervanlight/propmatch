"""
Konfigurasi terpusat untuk AI Agent Properti Harvey (PropMatch).

Semua konstanta penting (lokasi, bobot matching, path data, model AI)
dikumpulkan di sini supaya mudah disesuaikan tanpa mengubah logika inti.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Kredensial & integrasi (semua dari environment, tidak pernah hardcode)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

# Model AI (Gemini gratis). Flash untuk klasifikasi (cepat & murah).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Mock data hanya untuk testing lokal. Di produksi WAJIB "0" supaya
# data palsu tidak pernah mencemari database broker.
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "0") == "1"

# ---------------------------------------------------------------------------
# Sumber data scraper (multi-sumber, pluggable)
# ---------------------------------------------------------------------------
# Daftar scraper yang diaktifkan, dipisah koma. Pilihan: olx, threads, facebook.
ENABLED_SCRAPERS = [
    s.strip().lower()
    for s in os.getenv("ENABLED_SCRAPERS", "olx,threads,facebook").split(",")
    if s.strip()
]

# Jumlah maksimum item mentah yang diambil per scraper per run.
SCRAPER_LIMIT = int(os.getenv("SCRAPER_LIMIT", "25"))

# Facebook (sumber PEMBELI terkaya). Scraping butuh sesi login Harvey sendiri:
# isi cookie & ID grup yang dia ikuti. Tanpa ini, scraper Facebook dilewati.
FB_COOKIE = os.getenv("FB_COOKIE", "")
FB_GROUP_IDS = [g.strip() for g in os.getenv("FB_GROUP_IDS", "").split(",") if g.strip()]

# Threads (Meta): kata kunci pencarian publik untuk menangkap niat beli/jual.
THREADS_KEYWORDS = [
    k.strip() for k in os.getenv(
        "THREADS_KEYWORDS",
        "dicari rumah sidoarjo,cari rumah surabaya,butuh rumah sidoarjo,wtb rumah surabaya",
    ).split(",") if k.strip()
]

# Kata kunci niat-BELI (demand-side). Dipakai scraper untuk memfilter postingan
# yang kemungkinan besar berasal dari calon pembeli/penyewa — aset paling
# bernilai karena sisi penjual sudah melimpah di portal.
BUYER_KEYWORDS = [
    "dicari", "di cari", "cari rumah", "cari ruko", "cari tanah", "cari kos",
    "butuh rumah", "butuh ruko", "butuh kontrakan", "butuh kos", "nyari",
    "wtb", "want to buy", "minta info", "ada info", "rekomendasi rumah",
    "budget", "bujet", "maksimal", "max ", "siapa ada", "info dong",
]

# Wilayah fokus untuk memfilter listing yang relevan secara geografis.
TARGET_REGIONS = [
    "sidoarjo", "surabaya", "waru", "gedangan", "sedati", "taman", "krian",
    "sukodono", "candi", "buduran", "porong", "tanggulangin", "rungkut",
    "gunung anyar", "wonocolo", "wiyung", "lakarsantri", "sukolilo", "gubeng",
    "juanda", "aloha", "bungurasih",
]

# ---------------------------------------------------------------------------
# Path penyimpanan data
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DASHBOARD_OUTPUT = os.path.join(BASE_DIR, "index.html")
DASHBOARD_TEMPLATE = os.path.join(BASE_DIR, "dashboard", "template.html")

# ---------------------------------------------------------------------------
# Pengetahuan lokal: kelompok kecamatan yang berdekatan di Sidoarjo/Surabaya.
# Dipakai matcher untuk menilai kedekatan lokasi penjual <-> pencari.
# Setiap baris = satu klaster wilayah yang saling berdekatan / sering
# dianggap satu zona oleh pembeli.
# ---------------------------------------------------------------------------
LOCATION_CLUSTERS = [
    # Sidoarjo utara - perbatasan Surabaya (zona favorit komuter)
    ["waru", "aloha", "gedangan", "sedati", "buduran", "bandara juanda"],
    # Sidoarjo kota & sekitar
    ["sidoarjo kota", "sidoarjo", "sukodono", "wonoayu", "candi", "tanggulangin"],
    # Sidoarjo barat
    ["taman", "krian", "balongbendo", "tarik", "prambon", "wonoayu"],
    # Sidoarjo timur / pesisir
    ["porong", "jabon", "tulangan", "krembung"],
    # Surabaya selatan (berbatasan Sidoarjo)
    ["rungkut", "gunung anyar", "tenggilis", "wonocolo", "jambangan", "gayungan", "menanggal"],
    # Surabaya barat
    ["lakarsantri", "wiyung", "lidah", "sambikerep", "pakal", "benowo", "citraland"],
    # Surabaya timur
    ["sukolilo", "mulyorejo", "keputih", "gubeng", "tambaksari"],
    # Surabaya pusat
    ["tegalsari", "genteng", "bubutan", "simokerto"],
    # Surabaya utara
    ["kenjeran", "semampir", "pabean", "krembangan"],
]

# Pasangan indeks klaster yang saling bertetangga (berbatasan langsung), supaya
# lokasi berdekatan lintas-zona tetap dapat skor lebih tinggi daripada lokasi
# yang sama sekali tidak dikenali. Indeks mengacu ke urutan LOCATION_CLUSTERS.
ADJACENT_CLUSTERS = {
    frozenset({0, 1}),  # Sidoarjo utara <-> Sidoarjo kota
    frozenset({0, 2}),  # Sidoarjo utara <-> Sidoarjo barat
    frozenset({0, 4}),  # Waru/Gedangan <-> Rungkut/Gunung Anyar (perbatasan Sby-Sda)
    frozenset({1, 2}),  # Sidoarjo kota <-> barat
    frozenset({1, 3}),  # Sidoarjo kota <-> timur/pesisir
    frozenset({4, 5}),  # Surabaya selatan <-> barat
    frozenset({4, 6}),  # Surabaya selatan <-> timur
    frozenset({4, 7}),  # Surabaya selatan <-> pusat
    frozenset({5, 7}),  # Surabaya barat <-> pusat
    frozenset({6, 7}),  # Surabaya timur <-> pusat
    frozenset({7, 8}),  # Surabaya pusat <-> utara
    frozenset({6, 8}),  # Surabaya timur <-> utara
}

# ---------------------------------------------------------------------------
# Bobot penilaian matching (total = 100). Bisa di-tuning sesuai prioritas.
# ---------------------------------------------------------------------------
MATCH_WEIGHTS = {
    "lokasi": 40,        # kedekatan lokasi paling menentukan
    "harga": 35,         # budget pencari vs harga penjual
    "tipe": 20,          # tipe properti sama (rumah/ruko/tanah/dst)
    "pembayaran": 5,     # kecocokan metode bayar (KPR/cash)
}

# Skor minimum (0-100) agar sebuah pasangan dianggap "match" layak.
MATCH_THRESHOLD = 55

# Toleransi harga: pencari biasanya mau properti sampai +X% dari budget.
PRICE_OVER_BUDGET_TOLERANCE = 0.15  # 15% di atas budget masih dianggap cocok
