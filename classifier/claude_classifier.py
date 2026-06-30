"""
Klasifikasi & ekstraksi listing properti memakai Claude Haiku 4.5.

Mengubah teks mentah (judul iklan, pesan WA, postingan FB) menjadi JSON
terstruktur: status jual/cari, lokasi, harga, tipe, urgensi, kualitas lead, dll.

Memakai output_config structured outputs (json_schema) agar hasil DIJAMIN JSON
valid -- tidak perlu lagi regex parsing seperti pendekatan Gemini sebelumnya.
"""
import json
import time
import logging

import config

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """Anda adalah AI asisten broker properti ahli di wilayah Surabaya & Sidoarjo, Jawa Timur.
Baca data mentah berikut (bisa berupa iklan, pesan WhatsApp, atau postingan media sosial) lalu ekstrak informasinya.

DATA MENTAH:
\"\"\"
{raw_text}
\"\"\"

ATURAN PENTING:
1. "status" = JUAL jika pihak menjual/menawarkan properti; CARI jika pihak mencari/ingin beli/sewa; TIDAK_RELEVAN jika bukan tentang transaksi properti.
2. "harga" WAJIB berupa angka rupiah penuh (650 juta -> 650000000, 1,2 M -> 1200000000). Jika tidak disebut, isi 0.
3. "kualitas_lead" = HOT jika ada sinyal mendesak (BU, butuh cepat, harga di bawah pasar, sangat dicari); WARM jika normal & jelas; COLD jika info minim/ragu.
4. "lokasi" = kecamatan/daerah spesifik, contoh: "Waru, Sidoarjo".
5. "tipe_properti" = salah satu dari: Rumah, Ruko, Kos, Tanah, Apartemen, Gudang, Villa, Lainnya.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["JUAL", "CARI", "TIDAK_RELEVAN"]},
        "lokasi": {"type": "string"},
        "harga": {"type": "integer"},
        "tipe_properti": {"type": "string"},
        "LT_LB": {"type": "string"},
        "KT_KM": {"type": "string"},
        "kontak": {"type": "string"},
        "urgensi": {"type": "string", "enum": ["BU", "Cepat", "Normal"]},
        "metode_bayar": {"type": "string"},
        "kualitas_lead": {"type": "string", "enum": ["HOT", "WARM", "COLD"]},
        "catatan_ai": {"type": "string"},
    },
    "required": ["status", "lokasi", "harga", "tipe_properti", "urgensi",
                "kualitas_lead", "catatan_ai"],
    "additionalProperties": False,
}


class ClaudeClassifier:
    def __init__(self):
        self.api_key = config.ANTHROPIC_API_KEY
        self.client = None
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY tidak ada. Klasifikasi AI dinonaktifkan.")
            return
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as e:
            logger.error("Gagal inisialisasi Claude client: %s", e)

    def classify_property(self, raw_text: str, source_url: str = "",
                          source_name: str = "", retries: int = 2) -> dict:
        if not self.client:
            return {"status": "TIDAK_RELEVAN", "source_url": source_url,
                    "error": "Claude tidak aktif"}

        prompt = PROMPT_TEMPLATE.format(raw_text=raw_text.strip())

        last_err = None
        for attempt in range(retries + 1):
            try:
                response = self.client.messages.create(
                    model=config.CLAUDE_MODEL,
                    max_tokens=512,
                    output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
                    messages=[{"role": "user", "content": prompt}],
                )
                text = next(b.text for b in response.content if b.type == "text")
                data = json.loads(text)
                data["source_url"] = source_url
                data["source_name"] = source_name
                data["raw_text"] = raw_text.strip()
                return data
            except Exception as e:
                last_err = e
                logger.warning("Klasifikasi gagal (percobaan %d): %s", attempt + 1, e)
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))

        logger.error("Klasifikasi menyerah: %s", last_err)
        return {"status": "TIDAK_RELEVAN", "source_url": source_url,
                "source_name": source_name, "raw_text": raw_text.strip(),
                "error": str(last_err)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    classifier = ClaudeClassifier()
    test_text = ("Dijual cepat rumah di Waru Sidoarjo, dekat Bungurasih. Luas 6x15, 2 lantai. "
                 "KT 3 KM 2. Harga 750jt nego tipis. Bisa KPR. WA 08123456789. BU.")
    print(json.dumps(classifier.classify_property(test_text, "http://contoh.com"),
                      indent=2, ensure_ascii=False))
