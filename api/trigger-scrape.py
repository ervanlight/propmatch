"""
Picu workflow GitHub Actions yang menjalankan scraping penuh (serverless,
Vercel) -- dipicu tombol "Jalankan Scraping" di dashboard.

Kenapa tidak dijalankan langsung di sini: scraper Threads pakai Playwright
(browser Chromium headless) yang tidak bisa jalan di runtime serverless
Vercel, dan makan waktu 1-3 menit -- jauh di atas batas waktu fungsi
serverless. GitHub Actions (komputer GitHub, bukan batasan ketat itu) yang
benar-benar menjalankannya; fungsi ini cuma memicu lewat API lalu langsung
balas (tidak menunggu sampai selesai).
"""
import os
import sys
import json
import urllib.request
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api._auth import is_authorized, deny  # noqa: E402

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # format: "owner/repo"
WORKFLOW_FILE = "scrape.yml"


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not is_authorized(self.headers.get("Authorization", "")):
            deny(self)
            return

        try:
            if not GITHUB_TOKEN or not GITHUB_REPO:
                raise RuntimeError("GITHUB_TOKEN / GITHUB_REPO belum diset di environment Vercel.")

            url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
            req = urllib.request.Request(
                url,
                data=json.dumps({"ref": "master"}).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "User-Agent": "propmatch-dashboard",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()

            body = json.dumps({
                "ok": True,
                "message": "Scraping dimulai di GitHub Actions. Biasanya selesai 1-3 menit, "
                           "lalu refresh halaman ini untuk lihat data baru.",
                "monitor_url": f"https://github.com/{GITHUB_REPO}/actions",
            }).encode("utf-8")
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
