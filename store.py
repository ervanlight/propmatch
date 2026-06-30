"""
Storage layer berbasis SQLite (data/propmatch.db).

Menggantikan data/*.json (lihat migrate_json_to_sqlite.py untuk migrasi data
lama). Signature fungsi publik di sini SENGAJA dipertahankan sama seperti
versi JSON sebelumnya supaya main.py, delivery/handler.py, dan
dashboard/generator.py tidak perlu berubah banyak.
"""
import hashlib
import logging

import db
from models import normalize_listing, now_iso

logger = logging.getLogger(__name__)

_COLS = ["id", "lokasi", "lokasi_display", "harga", "tipe_properti", "lt_lb", "kt_km",
         "kontak", "urgensi", "metode_bayar", "kualitas_lead", "urgency_score",
         "catatan_ai", "source_url", "source_name", "source", "raw_text",
         "lead_status", "created_at", "updated_at", "deleted_at", "last_confirmed_at"]


def _table_for_status(status: str) -> str:
    return "sellers" if status == "JUAL" else "buyers"


def _row_to_dict(row) -> dict:
    d = dict(row)
    # Kembalikan nama field ke gaya lama (LT_LB/KT_KM) agar kompatibel dengan
    # matcher/dashboard yang sudah ada.
    d["LT_LB"] = d.pop("lt_lb", "")
    d["KT_KM"] = d.pop("kt_km", "")
    return d


def raw_hash(source_url: str, raw_text: str) -> str:
    basis = (source_url or "").strip().lower() or (raw_text or "").strip().lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def has_seen_raw(h: str) -> bool:
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT 1 FROM seen_raw WHERE hash = ?", (h,)).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_seen_raw(h: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO seen_raw (hash, created_at) VALUES (?, ?)",
                     (h, now_iso()))
        conn.commit()
    finally:
        conn.close()


def save_listing(raw: dict, source: str = None) -> str | None:
    """
    Simpan satu listing (hasil klasifikasi). Mengembalikan 'new', 'updated',
    atau None (kalau TIDAK_RELEVAN/diabaikan). Dedup berbasis id.
    """
    from classifier.urgency import compute_urgency_score

    item = normalize_listing(raw)
    if item["status"] not in ("JUAL", "CARI"):
        return None

    table = _table_for_status(item["status"])
    src = source or raw.get("source") or _guess_source(item.get("source_name", ""))
    urgency = compute_urgency_score(item.get("raw_text", ""))
    now = now_iso()

    conn = db.get_connection()
    try:
        existing = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item["id"],)).fetchone()

        if existing:
            existing = dict(existing)
            updates = {"updated_at": now, "deleted_at": None, "last_confirmed_at": now}
            for k in ("lokasi", "lokasi_display", "tipe_properti", "kontak", "urgensi",
                     "metode_bayar", "kualitas_lead", "catatan_ai", "source_url", "source_name"):
                v = item.get(k)
                if v and not existing.get(k):
                    updates[k] = v
            if item.get("harga") and not existing.get("harga"):
                updates["harga"] = item["harga"]
            if item.get("LT_LB") and not existing.get("lt_lb"):
                updates["lt_lb"] = item["LT_LB"]
            if item.get("KT_KM") and not existing.get("kt_km"):
                updates["kt_km"] = item["KT_KM"]
            updates["urgency_score"] = max(urgency, existing.get("urgency_score") or 0)
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?",
                        (*updates.values(), item["id"]))
            conn.commit()
            return "updated"

        conn.execute(f"""
            INSERT INTO {table} (id, lokasi, lokasi_display, harga, tipe_properti, lt_lb, kt_km,
                kontak, urgensi, metode_bayar, kualitas_lead, urgency_score, catatan_ai,
                source_url, source_name, source, raw_text, lead_status,
                created_at, updated_at, deleted_at, last_confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, NULL, ?)
        """, (item["id"], item["lokasi"], item["lokasi_display"], item["harga"],
              item["tipe_properti"], item["LT_LB"], item["KT_KM"], item["kontak"],
              item["urgensi"], item["metode_bayar"], item["kualitas_lead"], urgency,
              item["catatan_ai"], item["source_url"], item["source_name"], src,
              item["raw_text"], now, now, now))
        conn.commit()
        return "new"
    finally:
        conn.close()


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
    if "landing" in s:
        return "landing_page"
    return "telegram_forward"


def get_active(status: str) -> list:
    """Listing aktif (belum dihapus). 'closed' (deal selesai) dikecualikan secara
    default supaya tidak terus muncul sebagai kandidat match baru -- 'lost' tetap
    ikut, karena lead yang gagal sekali boleh dicocokkan ulang ke depannya."""
    table = _table_for_status(status)
    conn = db.get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE deleted_at IS NULL AND lead_status != 'closed'"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_penjual() -> list:
    return get_active("JUAL")


def get_pencari() -> list:
    return get_active("CARI")


def get_by_id(listing_id: str) -> dict | None:
    """Cari listing di kedua tabel (sellers lalu buyers) berdasarkan id."""
    conn = db.get_connection()
    try:
        for table in ("sellers", "buyers"):
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (listing_id,)).fetchone()
            if row:
                d = _row_to_dict(row)
                d["_table"] = table
                return d
        return None
    finally:
        conn.close()


def update_lead_status(listing_id: str, new_status: str) -> bool:
    """Update status lead (new/contacted/negotiating/closed/lost). True kalau ditemukan."""
    valid = {"new", "contacted", "negotiating", "closed", "lost"}
    if new_status not in valid:
        return False
    conn = db.get_connection()
    try:
        for table in ("sellers", "buyers"):
            cur = conn.execute(
                f"UPDATE {table} SET lead_status = ?, updated_at = ? WHERE id = ?",
                (new_status, now_iso(), listing_id))
            if cur.rowcount > 0:
                conn.commit()
                return True
        return False
    finally:
        conn.close()


def get_stale_contacted(days: int = 3) -> list:
    """Lead berstatus 'contacted' yang belum diupdate lebih dari `days` hari."""
    import datetime
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    conn = db.get_connection()
    try:
        out = []
        for table in ("sellers", "buyers"):
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE lead_status = 'contacted' AND updated_at < ? "
                "AND deleted_at IS NULL", (cutoff,)).fetchall()
            for r in rows:
                d = _row_to_dict(r)
                d["peran"] = "JUAL" if table == "sellers" else "CARI"
                out.append(d)
        return out
    finally:
        conn.close()


def save_matches(matches: list) -> None:
    conn = db.get_connection()
    try:
        conn.execute("DELETE FROM matches")
        now = now_iso()
        for m in matches:
            import json as _json
            conn.execute("""
                INSERT INTO matches (seller_id, buyer_id, skor, skor_10, urgency_score,
                    combined_score, rincian, alasan, alasan_ai, penjual_lokasi, penjual_harga,
                    penjual_tipe, penjual_url, penjual_kontak, pencari_lokasi, pencari_budget,
                    pencari_url, pencari_kontak, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (m.get("penjual_id"), m.get("pencari_id"), m.get("skor"), m.get("skor_10"),
                  m.get("urgency_score", 0), m.get("combined_score", m.get("skor")),
                  _json.dumps(m.get("rincian", {})), m.get("alasan", ""), m.get("alasan_ai", ""),
                  m.get("penjual_lokasi"), m.get("penjual_harga"), m.get("penjual_tipe"),
                  m.get("penjual_url"), m.get("penjual_kontak"), m.get("pencari_lokasi"),
                  m.get("pencari_budget"), m.get("pencari_url"), m.get("pencari_kontak"), now))
        conn.commit()
    finally:
        conn.close()


def get_matches() -> list:
    import json as _json
    conn = db.get_connection()
    try:
        rows = conn.execute("SELECT * FROM matches ORDER BY combined_score DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["rincian"] = _json.loads(d.get("rincian") or "{}")
            d["penjual_id"] = d.pop("seller_id")
            d["pencari_id"] = d.pop("buyer_id")
            out.append(d)
        return out
    finally:
        conn.close()


def save_meta(meta: dict) -> None:
    conn = db.get_connection()
    try:
        for k, v in meta.items():
            conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (k, str(v)))
        conn.commit()
    finally:
        conn.close()


def get_meta() -> dict:
    conn = db.get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


def soft_delete(status: str, listing_id: str) -> bool:
    table = _table_for_status(status)
    conn = db.get_connection()
    try:
        cur = conn.execute(f"UPDATE {table} SET deleted_at = ? WHERE id = ?",
                          (now_iso(), listing_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


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
