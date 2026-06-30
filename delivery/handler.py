"""
Otak bot interaktif Telegram.

Harvey cukup forward/paste pesan WA/FB/IG berisi info properti ke bot, lalu:
  1. AI mengklasifikasi & mengekstrak data terstruktur,
  2. data disimpan (dengan dedup) ke database,
  3. bot langsung mencari & membalas match terbaik saat itu juga.

Juga menangani perintah: /start, /stats, /top, /help, /hapus <id>.
Logika di sini dipakai bersama oleh bot polling (bot.py) dan webhook (api/telegram.py).
"""
import logging

import config
import store
from classifier.gemini_classifier import GeminiClassifier
from matcher import engine
from matcher.gemini_matcher import GeminiMatcher
from delivery.telegram_bot import esc, format_rupiah

logger = logging.getLogger(__name__)

_classifier = None
_ai_matcher = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = GeminiClassifier()
    return _classifier


def _get_ai_matcher():
    global _ai_matcher
    if _ai_matcher is None:
        _ai_matcher = GeminiMatcher()
    return _ai_matcher


def _build_help_text() -> str:
    text = (
        "🤖 <b>PropMatch — Asisten Properti Harvey</b>\n\n"
        "Cara pakai paling cepat:\n"
        "• <b>Forward / paste</b> pesan iklan atau permintaan properti (dari WA, FB, IG) ke sini.\n"
        "  Saya akan otomatis baca, simpan, lalu carikan pasangan yang cocok.\n\n"
        "Perintah:\n"
        "• /top — lihat 5 match terbaik saat ini\n"
        "• /stats — ringkasan jumlah data\n"
        "• /grup — link cepat ke grup Facebook properti Anda\n"
        "• /help — bantuan ini"
    )
    return text


def _build_groups_text() -> str:
    if not config.FB_GROUPS:
        return "Belum ada grup Facebook yang tersimpan."
    lines = ["📂 <b>Grup Facebook Properti Anda</b>",
             "<i>Buka, cari postingan \"dicari/butuh rumah...\", lalu forward ke sini.</i>\n"]
    for name, gid in config.FB_GROUPS.items():
        lines.append(f"• <a href='https://www.facebook.com/groups/{gid}'>{esc(name)}</a>")
    return "\n".join(lines)


HELP_TEXT = _build_help_text()


def _match_summary_line(m: dict, i: int) -> str:
    alasan = m.get("alasan_ai") or m.get("alasan", "")
    line = (
        f"\n<b>#{i} · Skor {m.get('skor_10', 0)}/10</b>\n"
        f"🏠 {esc(m.get('penjual_tipe', ''))} di {esc(m.get('penjual_lokasi', ''))}"
        f" — {format_rupiah(m.get('penjual_harga'))}\n"
        f"🔍 Pencari {esc(m.get('pencari_lokasi', ''))}"
        f" (budget {format_rupiah(m.get('pencari_budget'))})\n"
        f"💡 <i>{esc(alasan)}</i>\n"
    )
    if m.get("penjual_url"):
        line += f"🔗 <a href='{esc(m['penjual_url'])}'>Iklan penjual</a>\n"
    if m.get("penjual_kontak"):
        line += f"📞 {esc(m['penjual_kontak'])}\n"
    return line


def _handle_command(text: str) -> str:
    cmd = text.strip().split()[0].lower().lstrip("/")
    cmd = cmd.split("@")[0]  # buang @namabot di grup

    if cmd in ("start", "help"):
        return HELP_TEXT

    if cmd in ("grup", "group", "grupfb"):
        return _build_groups_text()

    if cmd == "stats":
        s = store.stats()
        return (
            "📊 <b>Ringkasan Database</b>\n"
            f"🏠 Penjual aktif: <b>{s['total_penjual']}</b>\n"
            f"🔍 Pencari aktif: <b>{s['total_pencari']}</b>\n"
            f"🔥 Lead HOT: <b>{s['total_hot']}</b>\n"
            f"🎯 Match tersimpan: <b>{s['total_match']}</b>"
        )

    if cmd == "top":
        matches = engine.find_matches(store.get_penjual(), store.get_pencari())
        if not matches:
            return "Belum ada match yang memenuhi skor minimum. Tambahkan lebih banyak data dulu 🙂"
        _get_ai_matcher().enrich_reasons(matches, limit=5)
        store.save_matches(matches)
        out = "🎯 <b>TOP MATCH SAAT INI</b>\n"
        for i, m in enumerate(matches[:5], 1):
            out += _match_summary_line(m, i)
        return out

    return ("Perintah tidak dikenal. Kirim /help untuk bantuan, atau langsung "
            "forward/paste info properti ke sini.")


def _handle_listing(text: str) -> str:
    classifier = _get_classifier()
    data = classifier.classify_property(text, source_url="", source_name="Telegram")
    status = str(data.get("status", "TIDAK_RELEVAN")).upper()

    if status not in ("JUAL", "CARI"):
        return ("🤔 Saya tidak yakin ini info jual/cari properti. "
                "Kalau ini memang listing, coba sertakan lokasi, harga, dan tipe propertinya.")

    result = store.save_listing(data)

    label = "PENJUAL" if status == "JUAL" else "PENCARI"
    prefix = "✅ Tersimpan" if result == "new" else "♻️ Diperbarui (sudah ada sebelumnya)"
    reply = (
        f"{prefix} sebagai <b>{label}</b>\n"
        f"🏠 {esc(data.get('tipe_properti', '-'))} · 📍 {esc(data.get('lokasi', '-'))}\n"
        f"💰 {format_rupiah(data.get('harga'))} · 🔥 {esc(data.get('kualitas_lead', '-'))}\n"
    )

    # Cari match lawan jenis untuk listing yang baru masuk.
    from models import normalize_listing
    item = normalize_listing(data)
    if status == "JUAL":
        matches = engine.find_matches([item], store.get_pencari())
    else:
        matches = engine.find_matches(store.get_penjual(), [item])

    if matches:
        _get_ai_matcher().enrich_reasons(matches, limit=3)
        reply += f"\n🎯 <b>Ketemu {len(matches)} kemungkinan match!</b>\n"
        for i, m in enumerate(matches[:3], 1):
            reply += _match_summary_line(m, i)
    else:
        reply += "\n🔍 Belum ada pasangan cocok di database. Saya simpan dulu, nanti dicocokkan otomatis."
    return reply


def process_message(text: str) -> str:
    """Titik masuk tunggal: tentukan apakah ini perintah atau listing, lalu proses."""
    if not text or not text.strip():
        return "Kirim teks info properti, atau /help untuk bantuan."
    text = text.strip()
    if text.startswith("/"):
        try:
            return _handle_command(text)
        except Exception as e:
            logger.exception("Error handle command")
            return f"⚠️ Terjadi error saat memproses perintah: {esc(e)}"
    try:
        return _handle_listing(text)
    except Exception as e:
        logger.exception("Error handle listing")
        return f"⚠️ Maaf, terjadi error saat memproses pesan: {esc(e)}"
