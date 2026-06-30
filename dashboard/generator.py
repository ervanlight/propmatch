"""
Generator dashboard statis.

Membaca data dari store lalu menyuntikkannya ke template HTML, menghasilkan
index.html yang siap dibuka di browser / di-deploy (Vercel, GitHub Pages, cPanel).
"""
import json
import logging

import config
import store

logger = logging.getLogger(__name__)


def generate_dashboard(output_path: str = None) -> str:
    output_path = output_path or config.DASHBOARD_OUTPUT

    payload = {
        "penjual": store.get_penjual(),
        "pencari": store.get_pencari(),
        "match": store.get_matches(),
        "meta": store.get_meta(),
        "stale_contacted": store.get_stale_contacted(days=3),
    }

    with open(config.DASHBOARD_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()

    html = template.replace(
        "/*__DATA__*/{}",
        json.dumps(payload, ensure_ascii=False),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard di-generate: %s", output_path)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generate_dashboard()
