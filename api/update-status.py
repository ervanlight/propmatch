"""
Update status lead ATAU status satu pasangan match (serverless, Vercel) --
dipicu tombol status di dashboard. Instan, langsung tulis ke Turso.

Body JSON:
  {"kind": "lead", "id": "...", "status": "contacted"}
  {"kind": "match", "seller_id": "...", "buyer_id": "...", "status": "closed"}
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
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw_body or b"{}")
            kind = payload.get("kind")
            status = payload.get("status")

            import store

            if kind == "lead":
                ok = store.update_lead_status(payload.get("id", ""), status)
            elif kind == "match":
                ok = store.update_match_status(payload.get("seller_id", ""),
                                               payload.get("buyer_id", ""), status)
            else:
                raise ValueError("kind harus 'lead' atau 'match'.")

            body = json.dumps({"ok": ok}).encode("utf-8")
            self.send_response(200 if ok else 404)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
