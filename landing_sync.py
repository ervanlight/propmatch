"""
Tarik lead baru dari landing page (relay Google Sheets) ke database SQLite.

Dipanggil dari main.py setiap pipeline harian berjalan. Data dari form sudah
terstruktur (bukan teks bebas) sehingga TIDAK perlu panggilan AI sama sekali
-- gratis sepenuhnya, beda dengan jalur scraper yang butuh Claude.
"""
import logging

import store
from database.google_sheets import GoogleSheetsLeads
from models import parse_harga

logger = logging.getLogger(__name__)


def _build_listing(kind: str, rec: dict) -> dict:
    status = "JUAL" if kind == "jual" else "CARI"
    catatan = rec.get("catatan", "")
    harga = parse_harga(rec.get("harga_min") or rec.get("harga_max") or 0)
    return {
        "status": status,
        "lokasi": rec.get("lokasi", ""),
        "harga": harga,
        "tipe_properti": rec.get("tipe_properti", "Lainnya"),
        "LT_LB": "",
        "KT_KM": "",
        "kontak": rec.get("wa", ""),
        "urgensi": "Normal",
        "metode_bayar": "",
        "kualitas_lead": "WARM",
        "catatan_ai": (f"Lead dari landing page ({rec.get('nama', '-')}). " + catatan).strip(),
        "source_url": rec.get("foto_url", ""),
        "source_name": "Landing Page",
        "raw_text": f"{rec.get('nama', '')} | {rec.get('lokasi', '')} | {catatan}",
    }


def sync_landing_leads() -> dict:
    """Tarik lead baru dari Sheets, simpan ke SQLite dengan source='landing_page'."""
    sheets = GoogleSheetsLeads()
    if not sheets.client:
        return {"jual": 0, "cari": 0}

    counts = {"jual": 0, "cari": 0}
    for kind in ("jual", "cari"):
        for rec in sheets.fetch_unsynced(kind):
            try:
                data = _build_listing(kind, rec)
                store.save_listing(data, source="landing_page")  # urgency dihitung otomatis dari raw_text
                sheets.mark_synced(kind, rec["_row"])
                counts[kind] += 1
            except Exception as e:
                logger.error("Gagal sync lead landing (%s, baris %s): %s", kind, rec.get("_row"), e)

    if counts["jual"] or counts["cari"]:
        logger.info("Sync landing page: %d jual, %d cari baru.", counts["jual"], counts["cari"])
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(sync_landing_leads())
