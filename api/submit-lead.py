"""
Endpoint penerima submit form landing page (serverless, untuk deploy ke Vercel).

Menerima POST JSON dari landing.html, lalu tulis ke Google Sheets (lihat
database/google_sheets.py untuk alasan kenapa bukan langsung ke SQLite --
filesystem Vercel tidak persisten). main.py menarik baris baru dari Sheets
ke SQLite setiap pipeline harian jalan.
"""
import os
import sys
import json
import re
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.google_sheets import GoogleSheetsLeads  # noqa: E402

REQUIRED_FIELDS = ["nama", "wa", "lokasi"]
MAX_FIELD_LEN = 500


def _clean(value: str) -> str:
    return str(value or "").strip()[:MAX_FIELD_LEN]


def _valid_phone(wa: str) -> bool:
    digits = re.sub(r"[^\d]", "", wa or "")
    return 9 <= len(digits) <= 15


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        self._send_json(200, {"ok": True, "message": "PropMatch lead intake aktif."})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body or b"{}")
        except Exception:
            self._send_json(400, {"ok": False, "error": "JSON tidak valid."})
            return

        kind = _clean(payload.get("type")).lower()
        if kind not in ("jual", "cari"):
            self._send_json(400, {"ok": False, "error": "Field 'type' harus 'jual' atau 'cari'."})
            return

        for f in REQUIRED_FIELDS:
            if not _clean(payload.get(f)):
                self._send_json(400, {"ok": False, "error": f"Field '{f}' wajib diisi."})
                return

        if not _valid_phone(payload.get("wa", "")):
            self._send_json(400, {"ok": False, "error": "Nomor WhatsApp tidak valid."})
            return

        data = {k: _clean(payload.get(k)) for k in
                ("nama", "wa", "lokasi", "harga_min", "harga_max", "tipe_properti",
                 "foto_url", "catatan")}

        try:
            sheets = GoogleSheetsLeads()
            ok = sheets.submit_lead(kind, data)
        except Exception as e:
            print("Submit lead error:", e)
            ok = False

        if ok:
            self._send_json(200, {"ok": True, "message": "Terima kasih! Data Anda sudah kami terima."})
        else:
            self._send_json(503, {"ok": False,
                                  "error": "Sistem sedang gangguan, coba lagi nanti atau hubungi kami langsung."})
