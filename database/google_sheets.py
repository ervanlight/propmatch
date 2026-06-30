"""
Relay lead dari landing page (form publik) ke sistem utama.

Kenapa lewat Google Sheets, bukan langsung tulis ke SQLite: file SQLite di
data/propmatch.db hanya persisten kalau ditulis oleh proses dengan disk yang
bertahan (bot.py yang jalan terus, atau main.py via GitHub Actions yang
commit balik ke repo). Fungsi serverless (Vercel) TIDAK punya filesystem
permanen -- tulisan ke file akan hilang begitu container daur ulang.

Google Sheets API justru didesain untuk ditulis dari mana saja, termasuk
serverless, dan selalu persisten. Jadi: landing page -> tulis ke Sheet (kotak
surat sementara) -> pipeline harian main.py membaca baris baru dari Sheet
dan memasukkannya ke SQLite (sumber kebenaran utama).
"""
import os
import json
import logging
import datetime

import config

logger = logging.getLogger(__name__)

SHEET_JUAL = "Leads_Jual"
SHEET_CARI = "Leads_Cari"
HEADER = ["timestamp", "nama", "wa", "lokasi", "harga_min", "harga_max",
         "tipe_properti", "foto_url", "catatan", "synced"]


class GoogleSheetsLeads:
    def __init__(self):
        self.sheet_url = config.GOOGLE_SHEET_URL
        self.client = None
        try:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials

            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = None
            if config.GOOGLE_CREDENTIALS_JSON:
                info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(info, scope)
            elif os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
                creds = ServiceAccountCredentials.from_json_keyfile_name(
                    config.GOOGLE_CREDENTIALS_FILE, scope)

            if creds:
                self.client = gspread.authorize(creds)
            else:
                logger.warning("Kredensial Google Sheets tidak ada. Relay lead nonaktif.")
        except Exception as e:
            logger.error("Gagal inisialisasi Google Sheets: %s", e)

    def _worksheet(self, tab_name: str):
        sheet = self.client.open_by_url(self.sheet_url)
        try:
            return sheet.worksheet(tab_name)
        except Exception:
            ws = sheet.add_worksheet(title=tab_name, rows=1000, cols=len(HEADER))
            ws.append_row(HEADER)
            return ws

    def submit_lead(self, kind: str, data: dict) -> bool:
        """kind = 'jual' atau 'cari'. Dipanggil dari api/submit-lead.py."""
        if not self.client or not self.sheet_url:
            logger.error("Google Sheets tidak terhubung -- lead TIDAK tersimpan.")
            return False
        tab = SHEET_JUAL if kind == "jual" else SHEET_CARI
        try:
            ws = self._worksheet(tab)
            row = [
                datetime.datetime.now().isoformat(timespec="seconds"),
                data.get("nama", ""),
                data.get("wa", ""),
                data.get("lokasi", ""),
                data.get("harga_min", data.get("harga", "")),
                data.get("harga_max", ""),
                data.get("tipe_properti", ""),
                data.get("foto_url", ""),
                data.get("catatan", ""),
                "",  # kolom 'synced' dikosongkan -- diisi main.py setelah ditarik ke SQLite
            ]
            ws.append_row(row)
            return True
        except Exception as e:
            logger.error("Gagal submit lead ke Sheets: %s", e)
            return False

    def fetch_unsynced(self, kind: str) -> list:
        """Ambil baris yang belum ditandai synced. Mengembalikan list dict + nomor baris."""
        if not self.client or not self.sheet_url:
            return []
        tab = SHEET_JUAL if kind == "jual" else SHEET_CARI
        try:
            ws = self._worksheet(tab)
            records = ws.get_all_records()  # baris 1 = header, otomatis dipakai sbg key
            out = []
            for i, rec in enumerate(records, start=2):  # baris data mulai dari 2
                if not str(rec.get("synced", "")).strip():
                    out.append({"_row": i, **rec})
            return out
        except Exception as e:
            logger.error("Gagal ambil lead dari Sheets: %s", e)
            return []

    def mark_synced(self, kind: str, row_number: int) -> None:
        if not self.client or not self.sheet_url:
            return
        tab = SHEET_JUAL if kind == "jual" else SHEET_CARI
        try:
            ws = self._worksheet(tab)
            col = HEADER.index("synced") + 1
            ws.update_cell(row_number, col, "OK")
        except Exception as e:
            logger.error("Gagal tandai synced di Sheets: %s", e)
