"""
Storage layer berbasis JSON dengan dedup, timestamp, dan soft-delete.

Ini menggantikan baca-tulis file JSON manual yang sebelumnya tersebar di
main.py dan google_sheets.py (penyebab data duplikat). Satu file per jenis:
  data/penjual.json  -> listing status JUAL
  data/pencari.json  -> listing status CARI
  data/match.json    -> hasil matching terbaru

Setiap record punya: id, created_at, updated_at, deleted_at (soft delete).
"""
import os
import json
import hashlib
import logging

import config
from models import normalize_listing, now_iso

logger = logging.getLogger(__name__)

PENJUAL_FILE = os.path.join(config.DATA_DIR, "penjual.json")
PENCARI_FILE = os.path.join(config.DATA_DIR, "pencari.json")
MATCH_FILE = os.path.join(config.DATA_DIR, "match.json")
META_FILE = os.path.join(config.DATA_DIR, "meta.json")
SEEN_FILE = os.path.join(config.DATA_DIR, "seen_raw.json")


def _ensure_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


def _read(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Gagal membaca %s: %s", path, e)
        return []


def _write(path: str, data) -> None:
    _ensure_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atomic, hindari file korup kalau proses mati di tengah


def _file_for_status(status: str) -> str:
    return PENJUAL_FILE if status == "JUAL" else PENCARI_FILE


def save_listing(raw: dict) -> str | None:
    """
    Simpan satu listing (hasil klasifikasi). Mengembalikan 'new', 'updated',
    atau None (kalau TIDAK_RELEVAN/diabaikan).
    Dedup berbasis id: kalau sudah ada, update timestamp & field kosong.
    """
    item = normalize_listing(raw)
    if item["status"] not in ("JUAL", "CARI"):
        return None

    path = _file_for_status(item["status"])
    items = _read(path)
    index = {it["id"]: it for it in items if "id" in it}

    if item["id"] in index:
        existing = index[item["id"]]
        existing["updated_at"] = now_iso()
        existing["deleted_at"] = None  # kalau muncul lagi, hidupkan kembali
        # Lengkapi field yang dulu kosong dengan data baru.
        for k, v in item.items():
            if v and not existing.get(k):
                existing[k] = v
        _write(path, items)
        return "updated"

    item["created_at"] = now_iso()
    item["updated_at"] = now_iso()
    item["deleted_at"] = None
    items.append(item)
    _write(path, items)
    return "new"


def get_active(status: str) -> list:
    """Ambil semua listing aktif (belum di-soft-delete) untuk status tertentu."""
    path = _file_for_status(status)
    return [it for it in _read(path) if not it.get("deleted_at")]


def get_penjual() -> list:
    return get_active("JUAL")


def get_pencari() -> list:
    return get_active("CARI")


def save_matches(matches: list) -> None:
    _write(MATCH_FILE, matches)


def get_matches() -> list:
    return _read(MATCH_FILE)


def save_meta(meta: dict) -> None:
    _write(META_FILE, meta)


def get_meta() -> dict:
    data = _read(META_FILE)
    return data if isinstance(data, dict) else {}


def soft_delete(status: str, listing_id: str) -> bool:
    path = _file_for_status(status)
    items = _read(path)
    for it in items:
        if it.get("id") == listing_id:
            it["deleted_at"] = now_iso()
            _write(path, items)
            return True
    return False


def raw_hash(source_url: str, raw_text: str) -> str:
    """ID stabil untuk konten mentah SEBELUM diklasifikasi AI. Dipakai untuk
    melewati panggilan AI sama sekali kalau konten ini sudah pernah diproses
    (mis. listing OLX yang sama masih tayang berhari-hari) -- penghematan
    biaya AI paling besar, karena listing sering muncul ulang di scraping
    harian padahal isinya tidak berubah."""
    basis = (source_url or "").strip().lower() or (raw_text or "").strip().lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def has_seen_raw(h: str) -> bool:
    seen = _read(SEEN_FILE)
    return h in (seen if isinstance(seen, list) else [])


def mark_seen_raw(h: str) -> None:
    seen = _read(SEEN_FILE)
    if not isinstance(seen, list):
        seen = []
    if h not in seen:
        seen.append(h)
        # Cap ukuran file -- simpan 5000 hash terbaru saja supaya tidak tumbuh tanpa batas.
        if len(seen) > 5000:
            seen = seen[-5000:]
        _write(SEEN_FILE, seen)


def stats() -> dict:
    penjual = get_penjual()
    pencari = get_pencari()
    matches = get_matches()
    hot = sum(1 for x in penjual + pencari if x.get("kualitas_lead") == "HOT")
    return {
        "total_penjual": len(penjual),
        "total_pencari": len(pencari),
        "total_match": len(matches),
        "total_hot": hot,
    }
