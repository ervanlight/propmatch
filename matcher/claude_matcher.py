"""
Lapisan penulis-alasan (opsional) untuk match, memakai Claude Haiku 4.5.

Matching utama dilakukan secara deterministik di matcher/engine.py. Modul ini
hanya memakai AI untuk menulis ulang alasan beberapa match teratas agar lebih
enak dibaca seperti catatan broker. Kalau API tidak tersedia / gagal, sistem
tetap jalan memakai alasan otomatis dari engine.
"""
import json
import logging

import config

logger = logging.getLogger(__name__)

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "alasan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "no": {"type": "integer"},
                    "teks": {"type": "string"},
                },
                "required": ["no", "teks"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["alasan"],
    "additionalProperties": False,
}


class ClaudeMatcher:
    def __init__(self):
        self.api_key = config.ANTHROPIC_API_KEY
        self.client = None
        if not self.api_key:
            return
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            logger.error("Gagal inisialisasi Claude matcher: %s", e)

    def enrich_reasons(self, matches: list, limit: int = 5) -> list:
        """Tulis ulang alasan untuk `limit` match teratas. Aman kalau gagal."""
        if not self.client or not matches:
            return matches

        top = matches[:limit]
        ringkas = [{
            "no": i + 1,
            "penjual": f"{m['penjual_tipe']} di {m['penjual_lokasi']} harga Rp{m['penjual_harga']:,}",
            "pencari": f"cari di {m['pencari_lokasi']} budget Rp{m['pencari_budget']:,}",
            "skor": m["skor"],
        } for i, m in enumerate(top)]

        prompt = (
            "Anda broker properti senior. Untuk setiap pasangan penjual-pencari berikut, "
            "tulis SATU kalimat alasan singkat (maksimal 20 kata) kenapa mereka layak "
            "dipertemukan, dalam Bahasa Indonesia gaya catatan broker yang to the point.\n\n"
            f"{json.dumps(ringkas, ensure_ascii=False, indent=2)}"
        )
        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
                messages=[{"role": "user", "content": prompt}],
            )
            text = next(b.text for b in response.content if b.type == "text")
            data = json.loads(text)
            by_no = {item.get("no"): item.get("teks", "") for item in data.get("alasan", [])}
            for i, match in enumerate(top):
                alasan = by_no.get(i + 1)
                if alasan:
                    match["alasan_ai"] = alasan
        except Exception as e:
            logger.warning("Gagal memperkaya alasan dengan AI (pakai alasan otomatis): %s", e)
        return matches
