"""
Status ringan (serverless, Vercel) -- dipoll dashboard setelah tombol
"Jalankan Scraping" diklik supaya bisa auto-refresh begitu selesai, tanpa
perlu nunggu redeploy atau reload manual berkali-kali. Sengaja terpisah dari
api/dashboard.py (yang generate HTML penuh + query semua tabel) karena ini
dipanggil berulang setiap beberapa detik selama scraping berjalan (1-3
menit) -- harus murah & instan.
"""
import os
import sys
import json
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api._auth import is_authorized, deny  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not is_authorized(self.headers.get("Authorization", "")):
            deny(self)
            return

        try:
            import store
            meta = store.get_meta()
            body = json.dumps({"ok": True, "meta": meta}).encode("utf-8")
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
