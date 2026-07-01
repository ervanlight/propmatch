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

logger = logging.getLogger(__name__)


def build_dashboard_html() -> str:
    payload = {
        "penjual": store.get_penjual(),
        "pencari": store.get_pencari(),
        "match": store.get_matches(),
        "meta": store.get_meta(),
        "stale_contacted": store.get_stale_contacted(days=3),
    }

    with open(config.DASHBOARD_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()

    return template.replace(
        "/*__DATA__*/{}",
        json.dumps(payload, ensure_ascii=False),
    )


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
