"""
Generator dashboard.

build_dashboard_html() menyusun HTML dari data TERKINI di database (Turso) --
dipakai oleh api/dashboard.py supaya dashboard live selalu menampilkan data
terbaru tiap kali dibuka, tanpa perlu regenerate file & redeploy.

generate_dashboard() (tulis ke index.html) dipertahankan untuk kebutuhan
lokal/debug (lihat file statis tanpa server), tapi BUKAN lagi yang dipakai
versi live di Vercel.
"""
import json
import logging

import config
import store
from matcher.engine import compute_price_arbitrage

logger = logging.getLogger(__name__)


def build_dashboard_html() -> str:
    penjual = store.get_penjual()
    payload = {
        "penjual": penjual,
        "pencari": store.get_pencari(),
        "match": store.get_matches(),
        "meta": store.get_meta(),
        "stale_contacted": store.get_stale_contacted(days=3),
        "price_arbitrage": compute_price_arbitrage(penjual),
    }

    with open(config.DASHBOARD_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()

    # json.dumps TIDAK escape "</script>" -- kalau ada raw_text/catatan_ai dari
    # sumber luar (scraping/forward Telegram) yang kebetulan (atau sengaja)
    # mengandung string itu, tag <script> di bawah bisa "ditutup" lebih awal
    # dan menyuntikkan HTML/JS lain ke dashboard yang sudah login. Escape jadi
    # "<\/script>" -- valid di JS string literal, tapi tidak lagi cocok
    # dengan penutup tag HTML manapun.
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    return template.replace("/*__DATA__*/{}", data_json)


def generate_dashboard(output_path: str = None) -> str:
    """Tulis snapshot dashboard ke file statis (dipakai untuk debug lokal)."""
    output_path = output_path or config.DASHBOARD_OUTPUT
    html = build_dashboard_html()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Dashboard snapshot ditulis: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_dashboard()
