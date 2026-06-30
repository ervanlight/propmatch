"""
Deteksi urgensi berbasis kata kunci (deterministik, GRATIS -- bukan panggilan
AI). Melengkapi 'kualitas_lead' (kategori HOT/WARM/COLD dari Claude) dengan
skor numerik 0-100 yang bisa dipakai untuk MENGURUTKAN lead dari paling
mendesak, sesuatu yang tidak bisa dilakukan kategori teks biasa.
"""
import re

# (kata kunci, bobot). Skor akhir = jumlah bobot yang cocok, dibatasi maks 100.
URGENCY_KEYWORDS = [
    (r"\bbu\b", 30),                      # "BU" = butuh uang
    (r"butuh\s*uang", 30),
    (r"butuh\s*cepat", 25),
    (r"\burgent\b", 25),
    (r"buru-?buru", 25),
    (r"dijual\s*cepat", 20),
    (r"jual\s*cepat", 20),
    (r"cari\s*cepat", 20),
    (r"\bcash\b", 15),
    (r"nego\s*tipis", 15),
    (r"harga\s*pas", 10),
    (r"siap\s*kpr", 5),
    (r"serius", 10),
    (r"\basap\b", 20),                    # "as soon as possible"
    (r"limited\s*time", 15),
    (r"hari\s*ini", 15),
    (r"minggu\s*ini", 10),
    (r"bulan\s*ini", 5),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), weight) for pat, weight in URGENCY_KEYWORDS]


def compute_urgency_score(raw_text: str) -> int:
    """Hitung skor urgensi 0-100 dari teks mentah listing/kebutuhan."""
    if not raw_text:
        return 0
    text = raw_text.lower()
    score = 0
    for pattern, weight in _COMPILED:
        if pattern.search(text):
            score += weight
    return min(score, 100)


if __name__ == "__main__":
    tests = [
        "Dijual cepat rumah Waru BU butuh uang nego tipis",
        "Dicari rumah Sidoarjo, budget 700jt, santai aja",
        "URGENT cash siap, harus closing minggu ini",
    ]
    for t in tests:
        print(compute_urgency_score(t), "-", t)
