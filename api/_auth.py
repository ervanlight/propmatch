"""
Helper HTTP Basic Auth dipakai bersama oleh semua endpoint di api/.

Dashboard & seluruh aksi (jalankan scraping, match ulang, paste & parse,
update status) berisi/menyentuh data kontak pribadi hasil scraping -- bukan
portal publik. Kredensial diset lewat environment variable Vercel:
DASHBOARD_USER (default "harvey") dan DASHBOARD_PASSWORD (wajib diisi).
"""
import os
import base64
import hmac

DASHBOARD_USER = os.getenv("DASHBOARD_USER", "harvey")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")


def is_authorized(auth_header: str) -> bool:
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


def deny(handler):
    handler.send_response(401)
    handler.send_header("WWW-Authenticate", 'Basic realm="PropMatch Dashboard"')
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(b"Login diperlukan.")
