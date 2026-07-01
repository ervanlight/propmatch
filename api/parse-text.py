"""
Terima teks yang ditempel dari medsos (serverless, Vercel) -- dipicu kotak
"Paste & Parse" di dashboard. AI klasifikasi lalu simpan ke Turso, sama
seperti forward ke bot Telegram, plus langsung cari kemungkinan match.
"""
import os
import sys
import json
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api._auth import is_authorized, deny  # noqa: E402

MAX_TEXT_LEN = 4000


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not is_authorized(self.headers.get("Authorization", "")):
            deny(self)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw_body or b"{}")
            text = str(payload.get("text", "")).strip()[:MAX_TEXT_LEN]
            if not text:
                raise ValueError("Teks kosong.")

            import store
            from models import normalize_listing
            from classifier.claude_classifier import ClaudeClassifier
            from matcher import engine
            from matcher.claude_matcher import ClaudeMatcher

            data = ClaudeClassifier().classify_property(text, source_url="", source_name="Dashboard (paste manual)")
            status = str(data.get("status", "TIDAK_RELEVAN")).upper()

            if status not in ("JUAL", "CARI"):
                body = json.dumps({
                    "ok": True, "relevan": False,
                    "message": "AI tidak yakin ini info jual/cari properti.",
                }).encode("utf-8")
                self.send_response(200)
            else:
                item = normalize_listing(data)
                result = store.save_listing(data, source="telegram_forward")

                if status == "JUAL":
                    matches = engine.find_matches([item], store.get_pencari())
                else:
                    matches = engine.find_matches(store.get_penjual(), [item])
                if matches:
                    try:
                        ClaudeMatcher().enrich_reasons(matches, limit=3)
                    except Exception:
                        pass
                    store.save_matches(matches)

                body = json.dumps({
                    "ok": True, "relevan": True,
                    "status_baru": result,
                    "data": {
                        "id": item["id"], "status": status,
                        "tipe_properti": item["tipe_properti"],
                        "lokasi_display": item["lokasi_display"],
                        "harga": item["harga"],
                    },
                    "match_ditemukan": len(matches),
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
