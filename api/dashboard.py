"""
Dashboard live (serverless, Vercel) -- render LANGSUNG dari Turso tiap
request, bukan file statis. Jadi begitu ada data baru (scraping, paste
manual, match ulang), refresh halaman langsung menampilkan yang terbaru
tanpa perlu redeploy.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api._auth import is_authorized, deny  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not is_authorized(self.headers.get("Authorization", "")):
            deny(self)
            return

        try:
            from dashboard.generator import build_dashboard_html
            html = build_dashboard_html()
        except Exception as e:
            html = f"<h1>Gagal memuat dashboard</h1><pre>{e}</pre>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
