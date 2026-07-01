"""
Matching engine deterministik (v2 — gate + score).

Mencocokkan penjual (JUAL) dengan pencari (CARI). Alur dua tahap:

  1. GERBANG PEMBATAL (hard gate) — pasangan yang melanggar batas mutlak
     LANGSUNG dibuang (bukan match), berapa pun tinggi skor dimensi lain:
       • tipe properti berbeda & dua-duanya spesifik,
       • harga jual jauh di atas budget (keduanya diketahui),
       • dua lokasi spesifik tapi zonanya jauh (bukan tetangga),
       • penjual & pencari ternyata kontak yang sama (self-match).
     Ini kunci presisi: tanpa gerbang, penjumlahan berbobot bisa "menutupi"
     ketidakcocokan fatal (mis. harga meleset 10x tertutup lokasi & tipe sama).

  2. SKOR BERBOBOT 0-100 untuk pasangan yang lolos gerbang: kedekatan lokasi,
     kecocokan budget vs harga, tipe, dan metode bayar. Kalau data kritis
     (harga/lokasi presisi) tidak diketahui, skor DIBATASI (INCOMPLETE_DATA_
     SCORE_CAP) dan diberi catatan — supaya match berdata tipis tidak tampil
     sebagai kecocokan tinggi yang menyesatkan.

Hasilnya konsisten, instan, gratis, dan bisa dijelaskan tanpa bergantung kuota
AI. Claude (matcher/claude_matcher.py) dipakai terpisah HANYA untuk menulis
kalimat alasan yang lebih enak dibaca pada beberapa match teratas.
"""
import logging

import config
from models import (location_clusters, normalize_lokasi, normalize_tipe,
                    normalize_phone, location_precision, plausible_price,
                    specific_location_tokens)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-skor per dimensi. Masing-masing mengembalikan dict:
#   {"score": 0-1, "incomplete": bool, ...gate flags}
# supaya score_pair bisa tahu bukan cuma "seberapa cocok" tapi juga "apakah
# datanya cukup" dan "apakah melanggar batas mutlak".
# ---------------------------------------------------------------------------
def _location_score(lok_jual: str, lok_cari: str) -> dict:
    a = normalize_lokasi(lok_jual)
    b = normalize_lokasi(lok_cari)
    if not a or not b:
        return {"score": 0.3, "incomplete": True, "far": False}

    pa, pb = location_precision(a), location_precision(b)
    both_specific = pa == "specific" and pb == "specific"

    # Menyebut kecamatan spesifik yang SAMA persis (mis. dua-duanya "waru").
    if specific_location_tokens(a) & specific_location_tokens(b):
        return {"score": 1.0, "incomplete": False, "far": False}

    ca, cb = location_clusters(a), location_clusters(b)
    if ca and cb:
        if ca & cb:  # berbagi zona wilayah
            score = 0.85 if both_specific else 0.7
            return {"score": score, "incomplete": not both_specific, "far": False}
        for i in ca:
            for j in cb:
                if frozenset({i, j}) in config.ADJACENT_CLUSTERS:
                    return {"score": 0.55, "incomplete": not both_specific, "far": False}
        # Dua-duanya dikenali zonanya tapi jauh & bukan tetangga.
        return {"score": 0.1, "incomplete": False, "far": both_specific}

    # Salah satu memuat yang lain secara teks (mis. "surabaya" vs "surabaya barat").
    if a in b or b in a:
        if pa == "city" and pb == "city":
            return {"score": 0.4, "incomplete": True, "far": False}
        return {"score": 0.6, "incomplete": not both_specific, "far": False}

    # Dua-duanya hanya level kota tapi kotanya beda (mis. "surabaya" vs "sidoarjo").
    if pa == "city" and pb == "city":
        return {"score": 0.2, "incomplete": True, "far": False}

    return {"score": 0.25, "incomplete": True, "far": False}


def _price_score(harga_jual: int, budget_cari: int) -> dict:
    """Harga penjual vs budget pencari. Harga di luar rentang wajar sudah
    di-nol-kan (plausible_price) oleh score_pair sebelum masuk sini."""
    if not harga_jual or not budget_cari:
        return {"score": 0.4, "incomplete": True, "over": False}

    if harga_jual <= budget_cari:
        ratio = harga_jual / budget_cari
        if ratio >= config.PRICE_TOO_CHEAP_RATIO:
            return {"score": 1.0, "incomplete": False, "over": False}
        # Jauh lebih murah dari budget -> kemungkinan beda kelas/spesifikasi.
        return {"score": 0.65, "incomplete": False, "over": False}

    over = (harga_jual - budget_cari) / budget_cari
    if over <= config.PRICE_OVER_BUDGET_TOLERANCE:
        return {"score": 0.8, "incomplete": False, "over": False}
    if over <= config.PRICE_HARD_OVER_TOLERANCE:
        return {"score": 0.4, "incomplete": False, "over": False}
    # Di atas batas keras -> pembatal (ditangani sebagai gate di score_pair).
    return {"score": 0.0, "incomplete": False, "over": True}


def _type_score(tipe_jual: str, tipe_cari: str) -> dict:
    a, b = normalize_tipe(tipe_jual), normalize_tipe(tipe_cari)
    if a == b and a != "lainnya":
        return {"score": 1.0, "incompatible": False}
    if "lainnya" in (a, b):
        # Salah satu pihak tidak spesifik -> netral, bukan pembatal.
        return {"score": 0.5, "incompatible": False}
    # Dua-duanya tipe konkret tapi berbeda -> pembatal.
    return {"score": 0.0, "incompatible": True}


def _payment_score(bayar_jual: str, bayar_cari: str) -> float:
    a = (bayar_jual or "").lower()
    b = (bayar_cari or "").lower()
    if not a or not b:
        return 0.5
    if "fleks" in a or "fleks" in b:
        return 1.0
    for key in ("kpr", "cash"):
        if key in a and key in b:
            return 1.0
    return 0.3


def score_pair(jual: dict, cari: dict) -> dict:
    """Nilai satu pasangan penjual-pencari. Selalu mengembalikan dict; kalau
    melanggar gerbang pembatal, dict-nya bertanda disqualified=True (skor 0)."""
    w = config.MATCH_WEIGHTS

    harga_jual = plausible_price(jual.get("harga", 0))
    budget_cari = plausible_price(cari.get("harga", 0))

    loc = _location_score(jual.get("lokasi"), cari.get("lokasi"))
    price = _price_score(harga_jual, budget_cari)
    tipe = _type_score(jual.get("tipe_properti"), cari.get("tipe_properti"))
    s_bayar = _payment_score(jual.get("metode_bayar"), cari.get("metode_bayar"))

    rincian = {
        "lokasi": round(loc["score"] * w["lokasi"]),
        "harga": round(price["score"] * w["harga"]),
        "tipe": round(tipe["score"] * w["tipe"]),
        "pembayaran": round(s_bayar * w["pembayaran"]),
    }

    base = {"skor": 0, "skor_10": 0.0, "rincian": rincian, "data_lengkap": True,
            "catatan": [], "disqualified": False, "dq_reason": ""}

    # ---- GERBANG PEMBATAL -------------------------------------------------
    if config.TYPE_STRICT_KNOCKOUT and tipe["incompatible"]:
        base.update(disqualified=True,
                    dq_reason=f"tipe beda ({jual.get('tipe_properti')} vs {cari.get('tipe_properti')})")
        return base
    if price["over"]:
        base.update(disqualified=True, dq_reason="harga jauh di atas budget")
        return base
    if config.LOCATION_FAR_KNOCKOUT and loc["far"]:
        base.update(disqualified=True, dq_reason="lokasi beda zona & berjauhan")
        return base

    # ---- SKOR BERBOBOT ----------------------------------------------------
    total = (loc["score"] * w["lokasi"] + price["score"] * w["harga"]
             + tipe["score"] * w["tipe"] + s_bayar * w["pembayaran"])
    skor = round(total)

    # Data kritis kurang -> batasi skor & beri catatan (jangan pura-pura yakin).
    catatan = []
    data_lengkap = True
    if price["incomplete"]:
        data_lengkap = False
        catatan.append("budget/harga belum diketahui — konfirmasi dulu")
    if loc["incomplete"]:
        data_lengkap = False
        catatan.append("lokasi belum spesifik — pastikan kecamatannya")

    if not data_lengkap and skor > config.INCOMPLETE_DATA_SCORE_CAP:
        skor = config.INCOMPLETE_DATA_SCORE_CAP

    base.update(skor=skor, skor_10=round(skor / 10, 1),
                data_lengkap=data_lengkap, catatan=catatan)
    return base


def _auto_reason(jual: dict, cari: dict, sc: dict) -> str:
    """Alasan ringkas otomatis (tanpa AI) — selalu tersedia sebagai fallback."""
    parts = []
    r = sc["rincian"]
    if r["lokasi"] >= config.MATCH_WEIGHTS["lokasi"] * 0.7:
        parts.append(f"lokasi berdekatan ({jual.get('lokasi_display') or jual.get('lokasi')})")
    if r["harga"] >= config.MATCH_WEIGHTS["harga"] * 0.7:
        parts.append("harga sesuai budget")
    if r["tipe"] >= config.MATCH_WEIGHTS["tipe"] * 0.9:
        parts.append(f"sama-sama {jual.get('tipe_properti')}")
    if not parts:
        parts.append("ada kecocokan parsial pada beberapa kriteria")
    reason = "Cocok karena " + ", ".join(parts) + "."
    if sc.get("catatan"):
        reason += " ⚠️ " + "; ".join(sc["catatan"]) + "."
    return reason


def find_matches(daftar_jual: list, daftar_cari: list, threshold: int = None,
                 top_n: int = 300) -> list:
    """
    Hasilkan daftar pasangan match di atas threshold, terurut dari skor
    tertinggi. Pasangan yang melanggar gerbang pembatal (tipe/harga/lokasi/
    self-match) TIDAK PERNAH ikut. Tiap match memuat ringkasan penjual &
    pencari supaya dashboard/Telegram bisa langsung menampilkannya.
    """
    if threshold is None:
        threshold = config.MATCH_THRESHOLD

    results = []
    for jual in daftar_jual:
        jual_phone = normalize_phone(jual.get("kontak", ""))
        for cari in daftar_cari:
            # Self-match: penjual & pencari kontak yang sama = mustahil jadi deal.
            cari_phone = normalize_phone(cari.get("kontak", ""))
            if jual_phone and cari_phone and jual_phone == cari_phone:
                continue

            sc = score_pair(jual, cari)
            if sc["disqualified"] or sc["skor"] < threshold:
                continue

            # Urgensi gabungan: ambil yang TERTINGGI antara penjual & pencari --
            # satu pihak mendesak saja sudah cukup alasan untuk diprioritaskan.
            urgency = max(jual.get("urgency_score", 0) or 0, cari.get("urgency_score", 0) or 0)
            # Skor gabungan untuk URUTAN tampil: kecocokan tetap dominan (80%),
            # urgensi menggeser lead mendesak ke atas tanpa mengubah makna 'skor'.
            combined = sc["skor"] * 0.8 + urgency * 0.2

            results.append({
                "skor": sc["skor"],
                "skor_10": sc["skor_10"],
                "rincian": sc["rincian"],
                "data_lengkap": sc["data_lengkap"],
                "urgency_score": urgency,
                "combined_score": round(combined, 1),
                "alasan": _auto_reason(jual, cari, sc),
                "alasan_ai": "",  # diisi belakangan oleh claude_matcher (opsional)
                "penjual_id": jual.get("id"),
                "penjual_lokasi": jual.get("lokasi_display") or jual.get("lokasi"),
                "penjual_harga": jual.get("harga"),
                "penjual_tipe": jual.get("tipe_properti"),
                "penjual_url": jual.get("source_url"),
                "penjual_kontak": jual.get("kontak"),
                "penjual_catatan": jual.get("catatan_ai"),
                "pencari_id": cari.get("id"),
                "pencari_lokasi": cari.get("lokasi_display") or cari.get("lokasi"),
                "pencari_budget": cari.get("harga"),
                "pencari_url": cari.get("source_url"),
                "pencari_kontak": cari.get("kontak"),
                "pencari_catatan": cari.get("catatan_ai"),
            })

    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results[:top_n]


PRICE_ARBITRAGE_THRESHOLD = 0.15   # minimal 15% di bawah rata-rata ZONA-nya
PRICE_ARBITRAGE_MIN_SAMPLE = 3     # per grup (tipe+zona), biar rata-ratanya bermakna


def compute_price_arbitrage(daftar_jual: list) -> list:
    """
    Cari penjual yang harganya jauh di bawah rata-rata -- tapi dibandingkan
    HANYA dengan penjual lain di ZONA WILAYAH yang sama (pakai klaster lokasi
    yang sama dengan matching, lihat models.location_clusters), bukan rata-
    rata seluruh kota. Rumah di Surabaya pusat vs pinggiran Sidoarjo beda
    kelas harga jauh walau sama-sama "rumah" -- dibandingkan mentah-mentah
    bikin rata-rata tidak bermakna (semua listing kelihatan "jauh di bawah
    rata-rata" padahal cuma beda zona).

    Listing yang lokasinya tidak dikenali klaster manapun dikelompokkan per
    teks lokasi persis (fallback lebih sempit, bukan digabung ke grup lain).
    Harga di luar rentang wajar (plausible_price) diabaikan supaya tidak
    merusak rata-rata.
    """
    groups = {}
    for jual in daftar_jual:
        harga = plausible_price(jual.get("harga"))
        if not harga:
            continue
        jual = {**jual, "harga": harga}
        tipe = normalize_tipe(jual.get("tipe_properti"))
        lokasi = normalize_lokasi(jual.get("lokasi"))
        clusters = location_clusters(lokasi)
        zone = min(clusters) if clusters else ("raw", lokasi)
        groups.setdefault((tipe, zone), []).append(jual)

    flagged = []
    for group in groups.values():
        if len(group) < PRICE_ARBITRAGE_MIN_SAMPLE:
            continue
        avg = sum(x["harga"] for x in group) / len(group)
        for jual in group:
            pct = (avg - jual["harga"]) / avg
            if pct >= PRICE_ARBITRAGE_THRESHOLD:
                flagged.append({
                    "id": jual.get("id"),
                    "tipe_properti": jual.get("tipe_properti"),
                    "lokasi_display": jual.get("lokasi_display") or jual.get("lokasi"),
                    "harga": jual["harga"],
                    "kontak": jual.get("kontak"),
                    "avg_price": round(avg),
                    "pct_below": round(pct, 3),
                    "sample_size": len(group),
                })

    flagged.sort(key=lambda x: x["pct_below"], reverse=True)
    return flagged
