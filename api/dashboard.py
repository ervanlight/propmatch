"""
Gerbang HTTP Basic Auth di depan dashboard (serverless, Vercel).

Dashboard (index.html) berisi data kontak pribadi penjual/pembeli hasil
scraping -- bukan portal publik (lihat knowledge/FEATURES.md: "Tidak ada
portal publik bagi user luar"). Maka akses harus login dulu, bukan URL
publik bebas siapapun.

Kredensial diset lewat environment variable Vercel (bukan hardcode):
DASHBOARD_USER (default "harvey") dan DASHBOARD_PASSWORD (wajib diisi).
"""
import os
import sys
import base64
import hmac
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DASHBOARD_USER = os.getenv("DASHBOARD_USER", "harvey")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")
INDEX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")


def _authorized(auth_header: str) -> bool:
    if not DASHBOARD_PASSWORD:
        return False  # kalau lupa diset, gagal aman (deny), bukan terbuka.
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        user, _, pw = decoded.partition(":")
    except Exception:
        return False
    return hmac.compare_digest(user, DASHBOARD_USER) and hmac.compare_digest(pw, DASHBOARD_PASSWORD)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _authorized(self.headers.get("Authorization", "")):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="PropMatch Dashboard"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Login diperlukan untuk akses dashboard.")
            return

        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                html = f.read()
        except FileNotFoundError:
            html = "<h1>Dashboard belum digenerate.</h1>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
