"""
Normalisasi & identitas listing.

Tujuan utama: memberi setiap listing ID stabil supaya tidak ada duplikat,
dan menstandarkan field (lowercase lokasi, harga jadi angka, dll) supaya
matcher & dashboard bisa mengandalkan bentuk data yang konsisten.
"""
import re
import hashlib
import datetime
from zoneinfo import ZoneInfo

import config


VALID_STATUS = {"JUAL", "CARI", "TIDAK_RELEVAN"}
VALID_TIPE = {"rumah", "ruko", "kos", "tanah", "apartemen", "gudang", "villa", "lainnya"}

# Semua timestamp di sistem ini WAJIB konsisten WIB (Asia/Jakarta), apapun
# timezone host yang menjalankan kodenya -- laptop lokal, GitHub Actions
# (Ubuntu runner, defaultnya UTC!), atau Vercel serverless. Tanpa ini,
# created_at/updated_at bisa beda 7 jam tergantung dijalankan dari mana,
# merusak perhitungan umur lead, rekap periode, dan dedup fuzzy berbasis
# tanggal (store.py).
try:
    _JAKARTA_TZ = ZoneInfo("Asia/Jakarta")
except Exception:
    # Fallback kalau paket tzdata entah kenapa tidak terpasang di suatu
    # environment (lihat requirements.txt) -- Indonesia tidak pakai DST,
    # jadi offset tetap UTC+7 ini selalu valid, cuma kehilangan lookup
    # nama zona resmi.
    _JAKARTA_TZ = datetime.timezone(datetime.timedelta(hours=7))


def now_wib() -> datetime.datetime:
    """Waktu SEKARANG di zona WIB, sebagai datetime naive (tanpa info
    timezone) -- supaya format string yang disimpan tetap sama seperti
    sebelumnya (tanpa suffix +07:00) dan tetap bisa dibandingkan/diurutkan
    apa adanya dengan timestamp lama yang sudah tersimpan."""
    return datetime.datetime.now(_JAKARTA_TZ).replace(tzinfo=None)


def now_iso() -> str:
    return now_wib().isoformat(timespec="seconds")


def format_tanggal(iso_str: str, with_time: bool = True) -> str:
    """Format tampilan WIB: DD-MM-YYYY (atau DD-MM-YYYY HH:MM WIB kalau
    with_time). Dipakai di dashboard & pesan Telegram -- BUKAN untuk
    disimpan (penyimpanan tetap format ISO YYYY-MM-DD supaya bisa
    diurutkan/dibandingkan sebagai string apa adanya)."""
    if not iso_str:
        return "-"
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
    except ValueError:
        return iso_str
    if with_time:
        return dt.strftime("%d-%m-%Y %H:%M") + " WIB"
    return dt.strftime("%d-%m-%Y")


def parse_harga(value) -> int:
    """Ubah berbagai format harga ('Rp 650jt', '1,2 M', 650000000) jadi integer rupiah."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).lower().strip()
    if not text:
        return 0

    # Tangani sufiks juta / miliar yang sering dipakai di listing Indonesia.
    multiplier = 1
    if re.search(r"\b(m|miliar|milyar|milir)\b", text) or text.endswith("m"):
        multiplier = 1_000_000_000
    elif re.search(r"\b(jt|juta)\b", text) or text.endswith("jt"):
        multiplier = 1_000_000

    # Ambil angka pertama (boleh desimal dengan koma/titik).
    num_match = re.search(r"(\d+[.,]?\d*)", text.replace(".", "").replace(" ", ""))
    if not num_match:
        # fallback: buang semua non-digit
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0

    raw = num_match.group(1).replace(",", ".")
    try:
        number = float(raw)
    except ValueError:
        return 0

    if multiplier > 1:
        return int(number * multiplier)
    # Tidak ada sufiks: anggap sudah angka penuh.
    return int(number)


def normalize_lokasi(value) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def location_clusters(text: str) -> set:
    """Klaster wilayah (index ke config.LOCATION_CLUSTERS) yang cocok dengan
    teks lokasi (SUDAH dinormalisasi). Dipakai untuk kedekatan lokasi
    matching (matcher/engine.py) SEKALIGUS untuk mengelompokkan listing per
    zona harga yang wajar dibandingkan (matcher/engine.py
    compute_price_arbitrage) -- rumah di Surabaya pusat dan rumah di
    pinggiran Sidoarjo tidak sebanding harganya walau sama-sama "rumah"."""
    found = set()
    for i, cluster in enumerate(config.LOCATION_CLUSTERS):
        for kec in cluster:
            if kec in text:
                found.add(i)
    return found


def normalize_phone(raw: str) -> str:
    """Normalisasi nomor HP Indonesia ke format internasional 62xxx tanpa
    simbol. Terima input mulai dari 0, +62, 62, atau dengan spasi/strip.
    Dipakai untuk bikin link wa.me (delivery/telegram_bot.py) SEKALIGUS
    sebagai kunci identitas untuk dedup lintas-sumber (store.py) -- nomor HP
    yang sama = kemungkinan besar orang yang sama, walau teks listing beda
    kata-kata di tiap channel."""
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("620"):
        digits = "62" + digits[3:]
    elif not digits.startswith("62"):
        digits = "62" + digits
    return digits


def normalize_tipe(value) -> str:
    if not value:
        return "lainnya"
    t = str(value).strip().lower()
    for valid in VALID_TIPE:
        if valid in t:
            return valid
    return "lainnya"


def make_id(data: dict) -> str:
    """
    ID stabil berbasis isi listing. Listing yang sama (sumber + lokasi + harga +
    tipe) akan menghasilkan ID identik sehingga otomatis ter-dedup.
    """
    source = (data.get("source_url") or "").strip().lower()
    if source and "mock" not in source:
        basis = source
    else:
        # Gunakan raw_text (teks sumber asli, stabil) — BUKAN catatan_ai yang
        # digenerate AI dan berubah tiap run sehingga merusak dedup.
        basis = "|".join([
            data.get("status", ""),
            normalize_lokasi(data.get("lokasi")),
            str(parse_harga(data.get("harga"))),
            normalize_tipe(data.get("tipe_properti")),
            (data.get("raw_text") or data.get("catatan_ai") or "")[:120].lower(),
        ])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def normalize_listing(data: dict) -> dict:
    """Standarkan satu listing hasil klasifikasi AI menjadi bentuk kanonik."""
    status = str(data.get("status", "TIDAK_RELEVAN")).upper().strip()
    if status not in VALID_STATUS:
        status = "TIDAK_RELEVAN"

    clean = {
        "status": status,
        "lokasi": normalize_lokasi(data.get("lokasi")),
        "lokasi_display": (str(data.get("lokasi")).strip() if data.get("lokasi") else ""),
        "harga": parse_harga(data.get("harga")),
        "tipe_properti": normalize_tipe(data.get("tipe_properti")),
        "LT_LB": str(data.get("LT_LB", "") or "").strip(),
        "KT_KM": str(data.get("KT_KM", "") or "").strip(),
        "kontak": str(data.get("kontak", "") or "").strip(),
        "urgensi": str(data.get("urgensi", "Normal") or "Normal").strip(),
        "metode_bayar": str(data.get("metode_bayar", "") or "").strip(),
        "kualitas_lead": str(data.get("kualitas_lead", "WARM") or "WARM").strip().upper(),
        "catatan_ai": str(data.get("catatan_ai", "") or "").strip(),
        "source_url": str(data.get("source_url", "") or "").strip(),
        "source_name": str(data.get("source_name", "") or "").strip(),
        "raw_text": str(data.get("raw_text", "") or "").strip(),
    }
    clean["id"] = make_id(clean)
    return clean
