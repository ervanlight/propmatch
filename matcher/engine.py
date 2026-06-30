"""
Matching engine deterministik.

Mencocokkan penjual (JUAL) dengan pencari (CARI) memakai skor 0-100 berbasis
aturan yang jelas: kedekatan lokasi, kecocokan budget vs harga, tipe properti,
dan metode pembayaran. Hasilnya konsisten, instan, gratis, dan bisa dijelaskan
ke Harvey tanpa bergantung pada kuota API AI.

Claude (matcher/claude_matcher.py) dipakai terpisah HANYA untuk menulis kalimat
alasan yang enak dibaca pada beberapa match teratas.
"""
import logging

import config
from models import normalize_lokasi, normalize_tipe

logger = logging.getLogger(__name__)


def _location_score(lok_jual: str, lok_cari: str) -> float:
    """0-1: 1 kalau lokasi sama, ~0.7 kalau satu klaster wilayah, 0 kalau jauh."""
    a = normalize_lokasi(lok_jual)
    b = normalize_lokasi(lok_cari)
    if not a or not b:
        return 0.3  # tidak tahu lokasi salah satu pihak -> netral rendah

    # Cocok persis / saling memuat (mis. "waru" vs "waru sidoarjo").
    if a == b or a in b or b in a:
        return 1.0

    # Cari token wilayah yang muncul di klaster yang sama.
    def clusters_of(text):
        found = set()
        for i, cluster in enumerate(config.LOCATION_CLUSTERS):
            for kec in cluster:
                if kec in text:
                    found.add(i)
        return found

    ca, cb = clusters_of(a), clusters_of(b)
    if ca and cb:
        if ca & cb:
            return 0.8   # berbagi klaster (satu zona)
        # Cek apakah ada pasangan klaster yang saling bertetangga.
        for i in ca:
            for j in cb:
                if frozenset({i, j}) in config.ADJACENT_CLUSTERS:
                    return 0.55  # zona berbeda tapi berbatasan langsung
        return 0.1       # dua-duanya dikenali tapi jauh
    return 0.25          # minimal salah satu tidak dikenali -> netral rendah


def _price_score(harga_jual: int, budget_cari: int) -> float:
    """0-1: seberapa cocok harga penjual dengan budget pencari."""
    if not harga_jual or not budget_cari:
        return 0.4  # salah satu tidak menyebut harga -> netral
    if harga_jual <= budget_cari:
        # Di bawah / pas budget = sangat bagus. Terlalu murah jauh sedikit kurang
        # ideal (mungkin beda kelas), tapi tetap layak.
        ratio = harga_jual / budget_cari
        if ratio >= 0.6:
            return 1.0
        return 0.7  # jauh di bawah budget, kemungkinan beda spesifikasi
    # Di atas budget: turun cepat, masih oke sampai toleransi.
    over = (harga_jual - budget_cari) / budget_cari
    if over <= config.PRICE_OVER_BUDGET_TOLERANCE:
        return 0.8
    if over <= 0.3:
        return 0.4
    return 0.0


def _type_score(tipe_jual: str, tipe_cari: str) -> float:
    a, b = normalize_tipe(tipe_jual), normalize_tipe(tipe_cari)
    if a == b and a != "lainnya":
        return 1.0
    if "lainnya" in (a, b):
        return 0.5  # pencari/penjual tidak spesifik
    return 0.0


def _payment_score(bayar_jual: str, bayar_cari: str) -> float:
    a = (bayar_jual or "").lower()
    b = (bayar_cari or "").lower()
    if not a or not b:
        return 0.5
    if "fleks" in a or "fleks" in b:
        return 1.0
    # KPR cocok dengan KPR, cash cocok dengan cash.
    for key in ("kpr", "cash"):
        if key in a and key in b:
            return 1.0
    return 0.3


def score_pair(jual: dict, cari: dict) -> dict:
    w = config.MATCH_WEIGHTS
    s_lok = _location_score(jual.get("lokasi"), cari.get("lokasi"))
    s_harga = _price_score(jual.get("harga", 0), cari.get("harga", 0))
    s_tipe = _type_score(jual.get("tipe_properti"), cari.get("tipe_properti"))
    s_bayar = _payment_score(jual.get("metode_bayar"), cari.get("metode_bayar"))

    total = (
        s_lok * w["lokasi"]
        + s_harga * w["harga"]
        + s_tipe * w["tipe"]
        + s_bayar * w["pembayaran"]
    )
    skor_100 = round(total)
    return {
        "skor": skor_100,
        "skor_10": round(skor_100 / 10, 1),
        "rincian": {
            "lokasi": round(s_lok * w["lokasi"]),
            "harga": round(s_harga * w["harga"]),
            "tipe": round(s_tipe * w["tipe"]),
            "pembayaran": round(s_bayar * w["pembayaran"]),
        },
    }


def _auto_reason(jual: dict, cari: dict, breakdown: dict) -> str:
    """Alasan ringkas otomatis (tanpa AI) sebagai fallback yang selalu tersedia."""
    parts = []
    r = breakdown["rincian"]
    if r["lokasi"] >= config.MATCH_WEIGHTS["lokasi"] * 0.7:
        parts.append(f"lokasi berdekatan ({jual.get('lokasi_display') or jual.get('lokasi')})")
    if r["harga"] >= config.MATCH_WEIGHTS["harga"] * 0.7:
        parts.append("harga sesuai budget")
    if r["tipe"] >= config.MATCH_WEIGHTS["tipe"] * 0.9:
        parts.append(f"sama-sama {jual.get('tipe_properti')}")
    if not parts:
        parts.append("ada kecocokan parsial pada beberapa kriteria")
    return "Cocok karena " + ", ".join(parts) + "."


def find_matches(daftar_jual: list, daftar_cari: list, threshold: int = None,
                 top_n: int = 30) -> list:
    """
    Hasilkan daftar pasangan match di atas threshold, terurut dari skor tertinggi.
    Tiap match memuat ringkasan penjual & pencari supaya dashboard/Telegram bisa
    langsung menampilkannya tanpa lookup lagi.
    """
    if threshold is None:
        threshold = config.MATCH_THRESHOLD

    results = []
    for jual in daftar_jual:
        for cari in daftar_cari:
            sc = score_pair(jual, cari)
            if sc["skor"] < threshold:
                continue
            results.append({
                "skor": sc["skor"],
                "skor_10": sc["skor_10"],
                "rincian": sc["rincian"],
                "alasan": _auto_reason(jual, cari, sc),
                "alasan_ai": "",  # diisi belakangan oleh claude_matcher (opsional)
                "penjual_id": jual.get("id"),
                "penjual_lokasi": jual.get("lokasi_display") or jual.get("lokasi"),
                "penjual_harga": jual.get("harga"),
                "penjual_tipe": jual.get("tipe_properti"),
                "penjual_url": jual.get("source_url"),
                "penjual_kontak": jual.get("kontak"),
                "pencari_id": cari.get("id"),
                "pencari_lokasi": cari.get("lokasi_display") or cari.get("lokasi"),
                "pencari_budget": cari.get("harga"),
                "pencari_url": cari.get("source_url"),
                "pencari_kontak": cari.get("kontak"),
            })

    results.sort(key=lambda x: x["skor"], reverse=True)
    return results[:top_n]
