"""
Sinkronisasi database (Turso) -> Google Sheets, sebagai "arsip yang selalu
rapi & bisa dicek kapan saja" di luar dashboard web.

Kenapa ini penting selain dashboard: dashboard butuh login & paham cara
bacanya; Google Sheets adalah format yang sudah familiar buat Harvey (dan
mudah dibagikan/di-filter/di-export sendiri tanpa bantuan teknis). Sheets
JUGA berfungsi sebagai arsip historis di luar Turso -- kalau suatu saat Turso
bermasalah, data terakhir tetap ada di Sheets.

Desain:
- 3 tab: "Penjual", "Pencari", "Ringkasan".
- Tiap sinkronisasi MENIMPA seluruh isi tab (bukan append) -- sumber
  kebenaran tetap Turso, Sheets murni cerminan terbaru supaya tidak pernah
  ada duplikat/data basi menumpuk di sana.
- Baris diurutkan dari yang PALING BARU masuk duluan, supaya lead terbaru
  langsung terlihat di atas tanpa perlu scroll/sort manual.
- Kalau kredensial belum diisi, sync dilewati (log warning) -- TIDAK membuat
  pipeline scraping gagal. Fitur ini murni tambahan, bukan jalur kritis.
"""
import logging

import config
from models import now_iso

logger = logging.getLogger(__name__)

SELLER_HEADERS = [
    "ID", "Nama", "No HP", "Jenis Properti", "Lokasi", "Harga Jual (Rp)",
    "LT/LB", "KT/KM", "Metode Bayar", "Urgensi", "Kualitas Lead",
    "Skor Urgensi", "Status Lead", "Sumber", "Link Sumber", "Catatan AI",
    "Tanggal Masuk", "Terakhir Diperbarui",
]

BUYER_HEADERS = [
    "ID", "Nama", "No HP", "Jenis Properti Dicari", "Lokasi Diinginkan",
    "Budget Maksimal (Rp)", "Metode Bayar", "Urgensi", "Kualitas Lead",
    "Skor Urgensi", "Status Lead", "Sumber", "Link Sumber", "Catatan AI",
    "Tanggal Masuk", "Terakhir Diperbarui",
]

SUMMARY_HEADERS = ["Metrik", "Nilai"]


def _get_client():
    """Bangun client gspread dari service account. Terima kredensial dari
    (urutan prioritas): variabel env berisi JSON penuh (cocok untuk
    Vercel/GitHub Actions -- tidak bisa simpan file), atau path file lokal
    (cocok untuk development di laptop)."""
    import json
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    if config.GOOGLE_SERVICE_ACCOUNT_JSON:
        info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    elif config.GOOGLE_SERVICE_ACCOUNT_FILE:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
    else:
        raise RuntimeError(
            "Kredensial Google Sheets belum diisi (GOOGLE_SERVICE_ACCOUNT_JSON "
            "atau GOOGLE_SERVICE_ACCOUNT_FILE di .env)."
        )
    return gspread.authorize(creds)


def _fmt_rupiah(angka) -> str:
    try:
        angka = int(angka)
    except (TypeError, ValueError):
        return ""
    if angka <= 0:
        return ""
    return f"{angka:,}".replace(",", ".")


def _seller_row(s: dict) -> list:
    return [
        s.get("id", ""),
        s.get("nama", "") or "",
        s.get("kontak", "") or "",
        s.get("tipe_properti", "") or "",
        s.get("lokasi_display") or s.get("lokasi") or "",
        _fmt_rupiah(s.get("harga")),
        s.get("LT_LB", "") or "",
        s.get("KT_KM", "") or "",
        s.get("metode_bayar", "") or "",
        s.get("urgensi", "") or "",
        s.get("kualitas_lead", "") or "",
        s.get("urgency_score", 0) or 0,
        s.get("lead_status", "") or "",
        s.get("source", "") or s.get("source_name", "") or "",
        s.get("source_url", "") or "",
        s.get("catatan_ai", "") or "",
        s.get("created_at", "") or "",
        s.get("updated_at", "") or "",
    ]


def _buyer_row(b: dict) -> list:
    return [
        b.get("id", ""),
        b.get("nama", "") or "",
        b.get("kontak", "") or "",
        b.get("tipe_properti", "") or "",
        b.get("lokasi_display") or b.get("lokasi") or "",
        _fmt_rupiah(b.get("harga")),
        b.get("metode_bayar", "") or "",
        b.get("urgensi", "") or "",
        b.get("kualitas_lead", "") or "",
        b.get("urgency_score", 0) or 0,
        b.get("lead_status", "") or "",
        b.get("source", "") or b.get("source_name", "") or "",
        b.get("source_url", "") or "",
        b.get("catatan_ai", "") or "",
        b.get("created_at", "") or "",
        b.get("updated_at", "") or "",
    ]


def _write_sheet(spreadsheet, tab_name: str, headers: list, rows: list) -> None:
    """Timpa seluruh isi satu tab dengan header + baris baru. Membuat tab
    kalau belum ada (setup pertama kali)."""
    try:
        ws = spreadsheet.worksheet(tab_name)
    except Exception:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=max(len(rows) + 10, 100),
                                       cols=max(len(headers) + 2, 10))

    ws.clear()
    values = [headers] + rows
    ws.update("A1", values, value_input_option="USER_ENTERED")
    # Baris header dibekukan & ditebalkan supaya tetap kelihatan saat scroll --
    # murni kosmetik, aman diabaikan kalau API berubah/gagal.
    try:
        ws.freeze(rows=1)
        ws.format("A1:Z1", {"textFormat": {"bold": True}})
    except Exception:
        pass


def sync_all() -> dict:
    """Tulis ulang tab Penjual, Pencari, dan Ringkasan dari data TERKINI di
    Turso. Aman dipanggil kapan saja (idempoten) -- selalu menimpa, tidak
    pernah menumpuk duplikat. Dipanggil otomatis di akhir tiap pipeline
    (main.py) -- tidak ada tombol manual, ini murni berjalan di belakang
    layar. Melempar exception kalau kredensial/spreadsheet ID belum diisi --
    main.py yang menangkap & melaporkan kegagalan ini lewat Telegram."""
    if not config.GOOGLE_SHEETS_ID:
        raise RuntimeError("GOOGLE_SHEETS_ID belum diisi di .env / environment.")

    import store

    client = _get_client()
    spreadsheet = client.open_by_key(config.GOOGLE_SHEETS_ID)

    penjual = sorted(store.get_penjual(), key=lambda x: x.get("created_at", ""), reverse=True)
    pencari = sorted(store.get_pencari(), key=lambda x: x.get("created_at", ""), reverse=True)

    _write_sheet(spreadsheet, "Penjual", SELLER_HEADERS, [_seller_row(s) for s in penjual])
    _write_sheet(spreadsheet, "Pencari", BUYER_HEADERS, [_buyer_row(b) for b in pencari])

    hot_penjual = sum(1 for s in penjual if s.get("kualitas_lead") == "HOT")
    hot_pencari = sum(1 for b in pencari if b.get("kualitas_lead") == "HOT")
    summary_rows = [
        ["Terakhir disinkronkan", now_iso() + " WIB"],
        ["Total Penjual Aktif", len(penjual)],
        ["Total Pencari Aktif", len(pencari)],
        ["Penjual HOT", hot_penjual],
        ["Pencari HOT", hot_pencari],
    ]
    _write_sheet(spreadsheet, "Ringkasan", SUMMARY_HEADERS, summary_rows)

    logger.info("Sinkronisasi Google Sheets selesai: %d penjual, %d pencari.",
               len(penjual), len(pencari))
    return {"penjual": len(penjual), "pencari": len(pencari)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(sync_all())
