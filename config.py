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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Model AI (Claude, berbayar tapi sangat murah). Haiku 4.5 cukup untuk tugas
# ekstraksi/klasifikasi sederhana ini -- ~3.000 klasifikasi per $5.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")

# Jeda antar panggilan klasifikasi (detik). Tier berbayar Claude punya limit
# permintaan/menit yang jauh lebih longgar daripada tier gratis Gemini, jadi
# default 0 (tanpa jeda). Naikkan lewat .env kalau suatu saat terjadi 429.
CLAUDE_CALL_DELAY_SECONDS = float(os.getenv("CLAUDE_CALL_DELAY_SECONDS", "0"))

# Mock data hanya untuk testing lokal. Di produksi WAJIB "0" supaya
# data palsu tidak pernah mencemari database broker.
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "0") == "1"

# ---------------------------------------------------------------------------
# Sumber data scraper (multi-sumber, pluggable)
# ---------------------------------------------------------------------------
# Daftar scraper yang diaktifkan, dipisah koma. Pilihan: olx, threads, facebook.
# Default difokuskan ke Threads saja: OLX hanya berisi listing JUAL (penjual),
# tidak pernah menghasilkan data PEMBELI yang justru jadi prioritas sistem ini.
# Ubah lewat env ENABLED_SCRAPERS kalau mau mengaktifkan ulang olx/facebook.
ENABLED_SCRAPERS = [
    s.strip().lower()
    for s in os.getenv("ENABLED_SCRAPERS", "threads").split(",")
    if s.strip()
]

# Jumlah maksimum item mentah yang diambil per scraper per run. Sebelumnya
# dibatasi 25 untuk menghemat kuota gratis Gemini; sekarang dengan Claude
# Haiku 4.5 (~$0.0016/klasifikasi) batasan itu tidak relevan lagi -> dinaikkan
# ke 100 untuk coverage lebih luas. 100 listing/sumber/hari x $0.0016 masih
# di bawah $0.50/hari.
SCRAPER_LIMIT = int(os.getenv("SCRAPER_LIMIT", "100"))

# Facebook Group (sumber PEMBELI terkaya) — dengan SENGAJA tidak di-scrape
# otomatis (lihat scraper/facebook_scraper.py untuk alasan privasi). Daftar ini
# hanya dipakai untuk menampilkan link cepat ("buka grup ini") di pesan bantuan
# bot, supaya Harvey gampang forward listing secara manual.
FB_GROUPS = {
    "Jual Beli Tanah Dan Property Surabaya Sidoarjo": "2996788917028288",
    "JUAL BELI RUMAH & TANAH WILAYAH SIDOARJO SURABAYA": "590137418706932",
    "Rumah Murah Surabaya": "947230525862360",
    "Property Surabaya": "837418913018544",
}

# Threads (Meta): kata kunci pencarian publik untuk menangkap niat beli/jual
# properti (scope produk: JUAL-BELI semua tipe, BUKAN sewa/kontrakan). PENTING:
# kata kunci PENDEK (2-3 kata) terbukti jauh lebih efektif daripada frasa
# panjang & spesifik — index pencarian Threads sering "No results" untuk frasa
# yang terlalu rinci (mis. "dicari rumah waru sidoarjo"), tapi mengembalikan
# banyak hasil untuk frasa umum (mis. "rumah sidoarjo", "jual rumah surabaya").
THREADS_KEYWORDS = [
    k.strip() for k in os.getenv(
        "THREADS_KEYWORDS",
        "rumah sidoarjo,rumah surabaya,jual rumah surabaya,cari rumah surabaya,"
        "ruko sidoarjo,tanah sidoarjo,apartemen surabaya,jual tanah sidoarjo",
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

# Kata kunci KONTEKS PROPERTI (sisi jual maupun cari). Dipakai scraper untuk
# memastikan sebuah postingan benar-benar soal properti SEBELUM dikirim ke AI —
# banyak postingan medsos menyebut nama wilayah ("surabaya", "taman", "candi")
# tapi sama sekali bukan soal properti. Tanpa filter ini, sampah non-properti
# ikut terklasifikasi & mencemari database (dan membuang kuota AI).
PROPERTY_KEYWORDS = [
    "rumah", "ruko", "tanah", "kavling", "kaveling", "apartemen", "apartement",
    "gudang", "villa", "vila", "kos", "kost", "hunian", "properti", "property",
    "dijual", "di jual", "jual", "dicari", "di cari", "wtb", "wts",
    "over kredit", "overkredit", "take over", "kpr", "shm", "hgb", "petok",
    "perumahan", "cluster", "kluster", "kpr subsidi", "nego",
]

# Wilayah fokus untuk memfilter listing yang relevan secara geografis.
TARGET_REGIONS = [
    "sidoarjo", "surabaya", "waru", "gedangan", "sedati", "taman", "krian",
    "sukodono", "candi", "buduran", "porong", "tanggulangin", "rungkut",
    "gunung anyar", "wonocolo", "wiyung", "lakarsantri", "sukolilo", "gubeng",
    "juanda", "aloha", "bungurasih",
]

# Nama kota/daerah yang terlalu LUAS untuk dianggap "lokasi presisi" saat
# matching. Dua listing yang cuma menyebut "surabaya" belum tentu berdekatan
# (Surabaya sangat besar) — jadi kecocokan lokasi mereka TIDAK boleh dinilai
# 100% seperti kalau sama-sama menyebut kecamatan spesifik ("waru").
VAGUE_LOCATION_TOKENS = {
    "surabaya", "sidoarjo", "sby", "sda", "surabaya kota",
    "jawa timur", "jatim", "jawatimur", "indonesia",
}

# Penanda WILAYAH LAIN di luar fokus Sidoarjo–Surabaya (dan ring terdekatnya).
# Kalau lokasi/teks JELAS menyebut salah satu ini DAN tidak menyebut wilayah
# target, listing ditolak di gerbang ingest (store.save_listing) supaya
# database tidak tercemar lead luar-area. Sengaja hanya memuat kota yang
# JELAS jauh (bukan ring Gerbangkertosusila seperti Gresik/Mojokerto yang
# masih mungkin dilayani Harvey) agar tidak salah-tolak lead yang valid.
OUT_OF_AREA_MARKERS = {
    "jakarta", "bekasi", "depok", "bogor", "tangerang", "serpong", "bsd",
    "cikarang", "karawang", "bandung", "cimahi", "semarang", "yogyakarta",
    "jogja", "sleman", "bantul", "solo", "surakarta", "malang", "kota malang",
    "kabupaten malang", "kediri", "madiun", "jember", "banyuwangi", "probolinggo",
    "bali", "denpasar", "badung", "medan", "makassar", "balikpapan", "samarinda",
    "pontianak", "batam", "pekanbaru", "palembang", "lampung", "manado",
}

# ---------------------------------------------------------------------------
# Path penyimpanan data
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

# Skor minimum (0-100) agar sebuah pasangan dianggap "match" layak. Dinaikkan
# dari 55 -> 60 seiring pemasangan aturan-pembatal (gate) di matcher: sekarang
# pasangan yang lolos gate memang harus benar-benar cocok, jadi ambang boleh
# lebih tinggi tanpa membuang match yang bagus.
MATCH_THRESHOLD = 60

# Toleransi harga LUNAK: pencari biasanya masih mau properti sampai +X% dari
# budget (dinilai bagus, bukan pembatal).
PRICE_OVER_BUDGET_TOLERANCE = 0.15  # 15% di atas budget masih dianggap cocok

# ---------------------------------------------------------------------------
# Aturan PEMBATAL (hard gate) matching. Ini kunci presisi: sebelum menghitung
# skor berbobot, pasangan yang melanggar salah satu batas mutlak di bawah
# LANGSUNG dibuang (bukan match), berapa pun tinggi skor dimensi lain. Tanpa
# ini, penjumlahan berbobot bisa "menutupi" ketidakcocokan fatal — mis. harga
# meleset 10x tertutup oleh lokasi & tipe yang kebetulan sama.
# ---------------------------------------------------------------------------
# Harga jual > budget +X% (KEDUANYA diketahui & masuk akal) -> BUKAN match.
PRICE_HARD_OVER_TOLERANCE = 0.25
# Harga jual < budget * X (mis. 10x lebih murah) -> mencurigakan (beda kelas/
# salah data), tidak dibatalkan tapi tidak diberi nilai penuh.
PRICE_TOO_CHEAP_RATIO = 0.30
# Tipe properti beda & dua-duanya spesifik (bukan "lainnya") -> BUKAN match.
TYPE_STRICT_KNOCKOUT = True
# Dua lokasi sama-sama spesifik (kecamatan dikenal) tapi zonanya jauh (bukan
# tetangga) -> BUKAN match.
LOCATION_FAR_KNOCKOUT = True

# Batas kewajaran harga properti di pasar Sidoarjo–Surabaya. Angka di luar
# rentang ini dianggap SALAH PARSE / bukan harga sungguhan, lalu diperlakukan
# sebagai "harga tidak diketahui" (bukan dipakai mentah). Contoh kasus nyata:
# AI/parser sesekali mengembalikan "650" (maksudnya 650 juta) sebagai 650 rupiah.
PRICE_MIN_PLAUSIBLE = 10_000_000          # Rp 10 juta
PRICE_MAX_PLAUSIBLE = 500_000_000_000     # Rp 500 miliar

# Kalau salah satu data KRITIS (harga/budget atau lokasi presisi) tidak
# diketahui, pasangan masih boleh muncul TAPI skornya dibatasi maksimum ini
# (mis. 6.9/10) dan diberi catatan "perlu konfirmasi" — supaya match berdata
# tipis tidak tampil sebagai kecocokan tinggi yang menyesatkan.
INCOMPLETE_DATA_SCORE_CAP = 69
