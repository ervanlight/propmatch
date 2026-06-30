"""
Klasifikasi & ekstraksi listing properti memakai Gemini.

Mengubah teks mentah (judul iklan, pesan WA, postingan FB) menjadi JSON
terstruktur: status jual/cari, lokasi, harga, tipe, urgensi, kualitas lead, dll.
"""
import os
import re
import json
import time
import logging

import config

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """Anda adalah AI asisten broker properti ahli di wilayah Surabaya & Sidoarjo, Jawa Timur.
Baca data mentah berikut (bisa berupa iklan, pesan WhatsApp, atau postingan media sosial) lalu ekstrak menjadi JSON valid.

DATA MENTAH:
\"\"\"
{raw_text}
\"\"\"

Hasilkan HANYA JSON (tanpa markdown, tanpa teks lain) dengan struktur persis:
{{
  "status": "JUAL | CARI | TIDAK_RELEVAN",
  "lokasi": "Kecamatan/daerah spesifik, contoh: Waru, Sidoarjo",
  "harga": 0,
  "tipe_properti": "Rumah | Ruko | Kos | Tanah | Apartemen | Gudang | Villa | Lainnya",
  "LT_LB": "luas tanah/luas bangunan, contoh 90/70 (kosongkan jika tidak ada)",
  "KT_KM": "jumlah kamar tidur/kamar mandi, contoh 3/2 (kosongkan jika tidak ada)",
  "kontak": "nomor WA/HP jika ada, jika tidak kosongkan",
  "urgensi": "BU | Cepat | Normal",
  "metode_bayar": "KPR | Cash | Fleksibel | (kosongkan jika tidak jelas)",
  "kualitas_lead": "HOT | WARM | COLD",
  "catatan_ai": "1-2 kalimat insight ringkas untuk broker"
}}

ATURAN PENTING:
1. "status" = JUAL jika pihak menjual/menawarkan properti; CARI jika pihak mencari/ingin beli/sewa; TIDAK_RELEVAN jika bukan tentang transaksi properti.
2. "harga" WAJIB berupa angka rupiah penuh (650 juta -> 650000000, 1,2 M -> 1200000000). Jika tidak disebut, isi 0.
3. "kualitas_lead" = HOT jika ada sinyal mendesak (BU, butuh cepat, harga di bawah pasar, sangat dicari); WARM jika normal & jelas; COLD jika info minim/ragu.
4. Output HARUS JSON valid yang bisa langsung di-parse.
"""


class GeminiClassifier:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.client = None
        if not self.api_key:
            logger.warning("GEMINI_API_KEY tidak ada. Klasifikasi AI dinonaktifkan.")
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.error("Gagal inisialisasi Gemini client: %s", e)

    @staticmethod
    def _extract_json(text: str):
        text = text.strip()
        # Buang pembungkus markdown ```json ... ```
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        # Ambil blok {...} pertama jika ada teks tambahan.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        return json.loads(text)

    # Circuit breaker: sekali kuota HARIAN terdeteksi habis, langsung berhenti
    # mencoba untuk sisa proses berjalan ini (retry tidak akan membantu sampai
    # kuota reset, jadi tidak perlu membuang waktu menunggu di tiap item).
    _daily_quota_exhausted = False

    def classify_property(self, raw_text: str, source_url: str = "",
                          source_name: str = "", retries: int = 2) -> dict:
        if not self.client:
            return {"status": "TIDAK_RELEVAN", "source_url": source_url,
                    "error": "Gemini tidak aktif"}

        if GeminiClassifier._daily_quota_exhausted:
            return {"status": "TIDAK_RELEVAN", "source_url": source_url,
                    "source_name": source_name, "raw_text": raw_text.strip(),
                    "error": "Kuota harian Gemini habis (dilewati tanpa retry)"}

        from google.genai import types
        prompt = PROMPT_TEMPLATE.format(raw_text=raw_text.strip())

        last_err = None
        for attempt in range(retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                data = self._extract_json(response.text)
                data["source_url"] = source_url
                data["source_name"] = source_name
                data["raw_text"] = raw_text.strip()
                return data
            except Exception as e:
                last_err = e
                msg = str(e)
                if "RESOURCE_EXHAUSTED" in msg and "PerDay" in msg:
                    logger.error("Kuota harian Gemini habis. Menghentikan retry untuk sisa proses.")
                    GeminiClassifier._daily_quota_exhausted = True
                    break
                logger.warning("Klasifikasi gagal (percobaan %d): %s", attempt + 1, e)
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))  # backoff sederhana

        logger.error("Klasifikasi menyerah: %s", last_err)
        return {"status": "TIDAK_RELEVAN", "source_url": source_url,
                "source_name": source_name, "raw_text": raw_text.strip(),
                "error": str(last_err)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    classifier = GeminiClassifier()
    test_text = ("Dijual cepat rumah di Waru Sidoarjo, dekat Bungurasih. Luas 6x15, 2 lantai. "
                 "KT 3 KM 2. Harga 750jt nego tipis. Bisa KPR. WA 08123456789. BU.")
    print(json.dumps(classifier.classify_property(test_text, "http://contoh.com"),
                      indent=2, ensure_ascii=False))
