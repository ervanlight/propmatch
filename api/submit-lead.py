"""
Endpoint penerima submit form landing page (serverless, untuk deploy ke Vercel).

Menulis LANGSUNG ke Turso lewat store.save_listing() -- tidak lewat Google
Sheets sebagai kotak surat sementara. Alasan desain lama (relay Sheets)
sudah tidak berlaku sejak migrasi ke Turso: Turso didesain persis untuk
ditulis dari mana saja termasuk serverless, sama seperti api/parse-text.py
dan api/dashboard.py. Data form sudah terstruktur (bukan teks bebas) jadi
TIDAK perlu panggilan AI sama sekali -- gratis sepenuhnya & instan (dulu lead
ini baru masuk sistem setelah Harvey klik "Jalankan Scraping" secara manual,
padahal ini justru sumber data paling siap-pakai).
"""
import os
import sys
import json
import re
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REQUIRED_FIELDS = ["nama", "wa", "lokasi"]
MAX_FIELD_LEN = 500
# Honeypot: field tersembunyi di form (lihat landing.html) yang manusia tidak
# akan pernah isi, tapi bot spam otomatis biasanya isi semua field yang ada.
HONEYPOT_FIELD = "website"


def _clean(value: str) -> str:
    return str(value or "").strip()[:MAX_FIELD_LEN]


def _valid_phone(wa: str) -> bool:
    digits = re.sub(r"[^\d]", "", wa or "")
    return 9 <= len(digits) <= 15


def _build_listing(kind: str, data: dict) -> dict:
    from models import parse_harga

    status = "JUAL" if kind == "jual" else "CARI"
    catatan = data.get("catatan", "")
    harga = parse_harga(data.get("harga_min") or data.get("harga_max") or 0)
    return {
        "status": status,
        "lokasi": data.get("lokasi", ""),
        "harga": harga,
        "tipe_properti": data.get("tipe_properti") or "Lainnya",
        "LT_LB": "",
        "KT_KM": "",
        "kontak": data.get("wa", ""),
        "urgensi": "Normal",
        "metode_bayar": "",
        "kualitas_lead": "WARM",
        "catatan_ai": (f"Lead dari landing page ({data.get('nama', '-')}). " + catatan).strip(),
        "source_url": data.get("foto_url", ""),
        "source_name": "Landing Page",
        "raw_text": f"{data.get('nama', '')} | {data.get('lokasi', '')} | {catatan}",
    }


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

        # Honeypot terisi -> hampir pasti bot. Balas sukses palsu (jangan
        # beri sinyal ke bot bahwa dia kena filter) tapi JANGAN simpan apapun.
        if _clean(payload.get(HONEYPOT_FIELD)):
            self._send_json(200, {"ok": True, "message": "Terima kasih! Data Anda sudah kami terima."})
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
            import store
            listing = _build_listing(kind, data)
            result = store.save_listing(listing, source="landing_page")
            ok = result is not None
        except Exception as e:
            print("Submit lead error:", e)
            ok = False

        if ok:
            self._send_json(200, {"ok": True, "message": "Terima kasih! Data Anda sudah kami terima."})
        else:
            self._send_json(503, {"ok": False,
                                  "error": "Sistem sedang gangguan, coba lagi nanti atau hubungi kami langsung."})
