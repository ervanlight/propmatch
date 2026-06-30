import os
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

class GoogleSheetsDB:
    def __init__(self):
        self.creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        self.sheet_url = os.getenv("GOOGLE_SHEET_URL")
        self.client = None
        
        try:
            if os.path.exists(self.creds_file):
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_file, scope)
                self.client = gspread.authorize(creds)
                logger.info("Berhasil terhubung ke Google Sheets API.")
            else:
                logger.warning(f"File {self.creds_file} tidak ditemukan. Menyimpan data secara lokal (mock DB).")
        except Exception as e:
            logger.error(f"Gagal inisialisasi Google Sheets: {e}")

    def save_listing(self, data: dict):
        """
        Menyimpan hasil ekstraksi AI ke Google Sheets.
        Jika belum ada credentials.json, simpan ke file lokal sementara.
        """
        if not self.client or not self.sheet_url:
            self._save_local(data)
            return

        try:
            sheet = self.client.open_by_url(self.sheet_url)
            
            # Tentukan tab berdasarkan status
            status = data.get("status", "")
            if status == "JUAL":
                worksheet = sheet.worksheet("Listing_Penjual")
            elif status == "CARI":
                worksheet = sheet.worksheet("Request_Pencari")
            else:
                return # Abaikan jika TIDAK_RELEVAN
                
            # Kolom: Tanggal, Source URL, Lokasi, Harga, Tipe, LT_LB, KT_KM, Kontak, Urgensi, Bayar, Kualitas, Catatan
            import datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [
                now,
                data.get("source_url", ""),
                data.get("lokasi", ""),
                data.get("harga", ""),
                data.get("tipe_properti", ""),
                data.get("LT_LB", ""),
                data.get("KT_KM", ""),
                data.get("kontak", ""),
                data.get("urgensi", ""),
                data.get("metode_bayar", ""),
                data.get("kualitas_lead", ""),
                data.get("catatan_ai", "")
            ]
            worksheet.append_row(row)
            logger.info("Berhasil menyimpan ke Google Sheets.")
            
        except Exception as e:
            logger.error(f"Gagal menyimpan ke Google Sheets: {e}")
            self._save_local(data)

    def _save_local(self, data: dict):
        """
        Penyimpanan sementara jika belum ada akses Google Sheets.
        """
        status = data.get("status", "TIDAK_RELEVAN")
        if status == "TIDAK_RELEVAN":
            return
            
        filename = f"local_db_{status.lower()}.json"
        
        # Baca data lama
        existing_data = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
            except:
                pass
                
        # Tambah data baru
        existing_data.append(data)
        
        # Simpan kembali
        with open(filename, 'w') as f:
            json.dump(existing_data, f, indent=4)
            
        logger.info(f"Data disimpan ke file lokal {filename}")
