"""
Picu sinkronisasi manual ke Google Sheets (serverless, Vercel) -- dipicu
tombol "Sinkronkan Google Sheets" di dashboard. Murni menulis ulang data
TERKINI dari Turso ke Sheets, tidak perlu scraping/AI, jadi cepat (~1-3 detik).
"""
import os
import sys
import json
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api._auth import is_authorized, deny  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not is_authorized(self.headers.get("Authorization", "")):
            deny(self)
            return

        try:
            from integrations.google_sheets import sync_all
            result = sync_all()
            body = json.dumps({
                "ok": True,
                "message": f"Tersinkron: {result['penjual']} penjual, {result['pencari']} pencari.",
            }).encode("utf-8")
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
