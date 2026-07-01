"""
Jalankan ulang mesin matching (serverless, Vercel) -- dipicu tombol
"Match Ulang" di dashboard. Murni hitung skor dari data yang sudah ada di
Turso, tidak perlu browser/scraping, jadi instan (~1-2 detik).
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
            import store
            from matcher import engine
            from matcher.claude_matcher import ClaudeMatcher
            from models import now_iso

            top_matches = engine.find_matches(store.get_penjual(), store.get_pencari())
            if top_matches:
                try:
                    ClaudeMatcher().enrich_reasons(top_matches, limit=5)
                except Exception:
                    pass  # alasan AI gagal-aman, alasan deterministik tetap ada
            result = store.save_matches(top_matches)
            store.save_meta({"last_match_run": now_iso()})

            body = json.dumps({
                "ok": True,
                "total_kandidat": len(top_matches),
                "baru": result["new"],
                "disegarkan": result["refreshed"],
            }).encode("utf-8")
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
