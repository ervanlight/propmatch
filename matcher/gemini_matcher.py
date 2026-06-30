"""
Lapisan penulis-alasan (opsional) untuk match.

Matching utama dilakukan secara deterministik di matcher/engine.py. Modul ini
hanya memakai Gemini untuk menulis ulang alasan beberapa match teratas agar
lebih enak dibaca seperti catatan broker. Kalau API tidak tersedia / gagal,
sistem tetap jalan memakai alasan otomatis dari engine.
"""
import re
import json
import logging

import config

logger = logging.getLogger(__name__)


class GeminiMatcher:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.client = None
        if not self.api_key:
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.error("Gagal inisialisasi Gemini matcher: %s", e)

    def enrich_reasons(self, matches: list, limit: int = 5) -> list:
        """Tulis ulang alasan untuk `limit` match teratas. Aman kalau gagal."""
        if not self.client or not matches:
            return matches

        from google.genai import types
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
            f"{json.dumps(ringkas, ensure_ascii=False, indent=2)}\n\n"
            'Balas HANYA JSON array: [{"no":1,"alasan":"..."}, ...]'
        )
        try:
            response = self.client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            text = response.text.strip()
            m = re.search(r"\[.*\]", text, re.DOTALL)
            arr = json.loads(m.group(0) if m else text)
            by_no = {item.get("no"): item.get("alasan", "") for item in arr}
            for i, match in enumerate(top):
                alasan = by_no.get(i + 1)
                if alasan:
                    match["alasan_ai"] = alasan
        except Exception as e:
            logger.warning("Gagal memperkaya alasan dengan AI (pakai alasan otomatis): %s", e)
        return matches
