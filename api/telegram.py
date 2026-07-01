"""
Webhook Telegram (serverless, untuk deploy ke Vercel).

Ini alternatif "selalu-aktif tanpa server" dari bot.py. Telegram mengirim setiap
pesan ke URL ini, fungsi memprosesnya, lalu membalas via API Telegram.

Penyimpanan: langsung baca-tulis ke Turso (lihat store.py/db.py) -- sama
seperti bot.py mode polling, listing baru TERSIMPAN PERMANEN di mode webhook
ini juga. Tidak ada lagi keterbatasan filesystem serverless karena database
satu-satunya adalah Turso (remote), bukan file lokal.

Setelah deploy, daftarkan webhook sekali:
  https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<app>.vercel.app/api/telegram
"""
import os
import sys
import json
from http.server import BaseHTTPRequestHandler

import requests

# Pastikan root project ada di path agar bisa import store/delivery/dll.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from delivery.handler import process_message  # noqa: E402


def _reply(chat_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
    except Exception:
        pass


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("PropMatch webhook aktif.".encode("utf-8"))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            update = json.loads(body or b"{}")
            msg = update.get("message") or update.get("channel_post") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            text = msg.get("text") or msg.get("caption") or ""
            if chat_id and text:
                reply = process_message(text)
                _reply(chat_id, reply)
        except Exception as e:
            # Selalu balas 200 ke Telegram agar tidak retry membabi buta.
            print("Webhook error:", e)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
