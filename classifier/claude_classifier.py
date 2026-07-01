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
Sistem ini KHUSUS jual-beli properti -- BUKAN sewa/kontrakan (semua tipe
properti: rumah, ruko, tanah, apartemen, kos, gudang, villa, boleh masuk,
ASALKAN transaksinya jual-beli, bukan sewa).
Baca data mentah berikut (bisa berupa iklan, pesan WhatsApp, atau postingan media sosial) lalu ekstrak informasinya DENGAN TELITI. Lebih baik menandai TIDAK_RELEVAN daripada memaksakan data yang meragukan masuk sebagai lead.

DATA MENTAH:
\"\"\"
{raw_text}
\"\"\"

ATURAN PENTING:
1. "status":
   - JUAL = pihak MENJUAL properti (transaksi beli-putus, bukan sewa).
   - CARI = pihak MENCARI/ingin MEMBELI properti untuk dimiliki (bukan cari sewa/kontrakan/kos).
   - TIDAK_RELEVAN = SEMUA kasus lain. WAJIB TIDAK_RELEVAN untuk: properti disewakan/dikontrakkan/kos harian-bulanan, pencari sewa/kontrakan, iklan JASA (kontraktor, arsitek, desain, renovasi, cleaning), iklan KPR/pinjaman/KTA/pegadaian/investasi, promosi agen/developer yang TIDAK menyebut properti konkret (cuma "hubungi kami, banyak pilihan"), lowongan kerja, dan apa pun yang bukan transaksi jual-beli satu properti konkret.
2. "harga" WAJIB angka rupiah penuh (650 juta -> 650000000; 1,2 M -> 1200000000; 1.5 miliar -> 1500000000). JANGAN pernah keliru satuan (jangan tulis 650 untuk "650 juta"). Untuk status CARI, isi "harga" = BUDGET MAKSIMUM pencari (batas atas); kalau disebut rentang "500-700jt", ambil 700000000. Jika harga/budget tidak disebut, isi 0.
3. "kualitas_lead" = HOT jika ada sinyal mendesak (BU, butuh cepat, harga di bawah pasar, sangat dicari); WARM jika normal & jelas; COLD jika info minim/ragu.
4. "lokasi" = kecamatan/daerah spesifik + kota, contoh: "Waru, Sidoarjo". Kalau hanya kota tanpa kecamatan, tulis kotanya saja. Kalau tidak ada info lokasi, isi "".
5. "tipe_properti" = salah satu: Rumah, Ruko, Kos, Tanah, Apartemen, Gudang, Villa, Lainnya.
6. "dalam_wilayah" = true HANYA jika properti berada di Surabaya, Sidoarjo, atau sekitarnya langsung (Gedangan, Waru, Taman, Krian, dst). false jika jelas di kota/wilayah lain (Jakarta, Malang, Bali, dll). Jika lokasi tidak diketahui, isi true (jangan buang lead karena ragu).
7. "is_agen" = true jika postingan jelas dari agen/broker/developer yang menawarkan BANYAK unit atau menyebar iklan massal; false jika tampak dari pemilik langsung atau pencari perorangan.
8. "keyakinan" = 0-100, seberapa yakin Anda klasifikasi ini benar & datanya bisa dipakai (rendah kalau teks ambigu/minim).
9. "catatan_ai" = MAKSIMAL 15 kata, satu kalimat singkat.
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
        "dalam_wilayah": {"type": "boolean"},
        "is_agen": {"type": "boolean"},
        "keyakinan": {"type": "integer"},
        "catatan_ai": {"type": "string"},
    },
    "required": ["status", "lokasi", "harga", "tipe_properti", "urgensi",
                "kualitas_lead", "dalam_wilayah", "keyakinan", "catatan_ai"],
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
                    max_tokens=300,
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
