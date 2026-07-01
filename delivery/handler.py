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
from classifier.claude_classifier import ClaudeClassifier
from matcher import engine
from matcher.claude_matcher import ClaudeMatcher
from delivery.telegram_bot import (esc, format_rupiah, wa_link,
                                    draft_pesan_penjual, draft_pesan_pencari)

logger = logging.getLogger(__name__)

_classifier = None
_ai_matcher = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = ClaudeClassifier()
    return _classifier


def _get_ai_matcher():
    global _ai_matcher
    if _ai_matcher is None:
        _ai_matcher = ClaudeMatcher()
    return _ai_matcher


def _build_help_text() -> str:
    text = (
        "🤖 <b>PropMatch — Asisten Properti Harvey</b>\n\n"
        "Cara pakai paling cepat:\n"
        "• <b>Forward / paste</b> pesan iklan atau permintaan properti (dari WA, FB, IG) ke sini.\n"
        "  Saya akan otomatis baca, simpan, lalu carikan pasangan yang cocok.\n\n"
        "Perintah:\n"
        "• /top — lihat 5 match terbaik saat ini (HOT &amp; mendesak di atas)\n"
        "• /stats — ringkasan jumlah data\n"
        "• /status &lt;id&gt; &lt;status&gt; — update status lead "
        "(new/contacted/negotiating/closed/lost)\n"
        "• /matchstatus &lt;id_penjual&gt; &lt;id_pencari&gt; &lt;status&gt; — tandai SATU "
        "pasangan match (potential/contacted/negotiating/closed/lost)\n"
        "• /hapus &lt;id&gt; — buang listing salah-klasifikasi/duplikat/spam\n"
        "• /reminder — lead 'contacted' yang belum di-follow-up &gt;3 hari\n"
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
    urgensi_badge = " 🔥" if m.get("urgency_score", 0) >= 50 else ""
    line = (
        f"\n<b>#{i} · Skor {m.get('skor_10', 0)}/10{urgensi_badge}</b>\n"
        f"🏠 {esc(m.get('penjual_tipe', ''))} di {esc(m.get('penjual_lokasi', ''))}"
        f" — {format_rupiah(m.get('penjual_harga'))}"
        f" <code>#{esc(m.get('penjual_id', ''))}</code>\n"
        f"🔍 Pencari {esc(m.get('pencari_lokasi', ''))}"
        f" (budget {format_rupiah(m.get('pencari_budget'))})"
        f" <code>#{esc(m.get('pencari_id', ''))}</code>\n"
        f"💡 <i>{esc(alasan)}</i>\n"
    )
    links = []
    if m.get("penjual_url"):
        links.append(f"🔗 <a href='{esc(m['penjual_url'])}'>Iklan penjual</a>")
    if m.get("pencari_url"):
        links.append(f"🔗 <a href='{esc(m['pencari_url'])}'>Postingan pencari</a>")
    if links:
        line += " · ".join(links) + "\n"
    wa_p = wa_link(m.get("penjual_kontak", ""),
                  draft_pesan_penjual(m.get("penjual_lokasi", ""), m.get("penjual_tipe", "")))
    wa_c = wa_link(m.get("pencari_kontak", ""),
                  draft_pesan_pencari(m.get("pencari_lokasi", ""), m.get("pencari_budget")))
    if wa_p:
        line += f"💬 <a href='{esc(wa_p)}'>WA Penjual</a>"
    if wa_c:
        line += (" · " if wa_p else "") + f"<a href='{esc(wa_c)}'>WA Pencari</a>"
    if wa_p or wa_c:
        line += "\n"
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
        out = "🎯 <b>TOP MATCH SAAT INI</b> (urutan: kecocokan + urgensi)\n"
        for i, m in enumerate(matches[:5], 1):
            out += _match_summary_line(m, i)
        return out

    if cmd == "status":
        return _handle_status_command(text)

    if cmd == "matchstatus":
        return _handle_matchstatus_command(text)

    if cmd == "hapus":
        return _handle_hapus_command(text)

    if cmd == "reminder":
        return _handle_reminder_command()

    return ("Perintah tidak dikenal. Kirim /help untuk bantuan, atau langsung "
            "forward/paste info properti ke sini.")


VALID_LEAD_STATUS = ("new", "contacted", "negotiating", "closed", "lost")


def _handle_status_command(text: str) -> str:
    parts = text.strip().split()
    if len(parts) != 3:
        return ("Format: <code>/status &lt;id&gt; &lt;status&gt;</code>\n"
                f"Status valid: {', '.join(VALID_LEAD_STATUS)}\n"
                "Contoh: <code>/status c9af544f91cb346e contacted</code>\n"
                "(ID bisa dilihat di hasil /top, tertera di bawah lokasi)")

    listing_id, new_status = parts[1], parts[2].lower()
    if new_status not in VALID_LEAD_STATUS:
        return f"Status tidak dikenal. Pilih salah satu: {', '.join(VALID_LEAD_STATUS)}"

    item = store.get_by_id(listing_id)
    if not item:
        return f"ID <code>{esc(listing_id)}</code> tidak ditemukan."

    store.update_lead_status(listing_id, new_status)
    label = f"{item.get('tipe_properti', '-')} di {item.get('lokasi_display') or item.get('lokasi', '-')}"
    return f"✅ Status <b>{esc(label)}</b> diubah jadi <b>{esc(new_status)}</b>."


def _handle_matchstatus_command(text: str) -> str:
    parts = text.strip().split()
    if len(parts) != 4:
        return ("Format: <code>/matchstatus &lt;id_penjual&gt; &lt;id_pencari&gt; &lt;status&gt;</code>\n"
                f"Status valid: {', '.join(store.VALID_MATCH_STATUS)}\n"
                "Contoh: <code>/matchstatus c9af544f91cb346e 2baa768fbd573bfc contacted</code>")

    seller_id, buyer_id, new_status = parts[1], parts[2], parts[3].lower()
    if new_status not in store.VALID_MATCH_STATUS:
        return f"Status tidak dikenal. Pilih salah satu: {', '.join(store.VALID_MATCH_STATUS)}"

    ok = store.update_match_status(seller_id, buyer_id, new_status)
    if not ok:
        return "Pasangan match itu tidak ditemukan di database."
    return f"✅ Match <code>{esc(seller_id)}</code> × <code>{esc(buyer_id)}</code> ditandai <b>{esc(new_status)}</b>."


def _handle_hapus_command(text: str) -> str:
    parts = text.strip().split()
    if len(parts) != 2:
        return ("Format: <code>/hapus &lt;id&gt;</code>\n"
                "Buang listing salah-klasifikasi/duplikat/spam dari database "
                "(soft-delete, tidak muncul lagi di dashboard/matching).\n"
                "(ID bisa dilihat di hasil /top, tertera di bawah lokasi)")

    listing_id = parts[1]
    item = store.get_by_id(listing_id)
    if not item:
        return f"ID <code>{esc(listing_id)}</code> tidak ditemukan."

    status = "JUAL" if item.get("_table") == "sellers" else "CARI"
    store.soft_delete(status, listing_id)
    label = f"{item.get('tipe_properti', '-')} di {item.get('lokasi_display') or item.get('lokasi', '-')}"
    return f"🗑️ <b>{esc(label)}</b> <code>#{esc(listing_id)}</code> sudah dibuang dari database."


def _handle_reminder_command() -> str:
    stale = store.get_stale_contacted(days=3)
    if not stale:
        return "👍 Tidak ada lead 'contacted' yang terbengkalai >3 hari. Aman."

    out = f"⏰ <b>{len(stale)} Lead Perlu Di-follow-up</b> (contacted &gt;3 hari, belum diupdate)\n"
    for item in stale[:15]:
        label = f"{item.get('tipe_properti', '-')} di {item.get('lokasi_display') or item.get('lokasi', '-')}"
        wa = wa_link(item.get("kontak", ""),
                    f"Halo, mau follow-up soal {item.get('tipe_properti', 'properti')} "
                    f"di {item.get('lokasi_display') or item.get('lokasi', '')}. "
                    f"Apakah masih berminat?")
        out += (f"\n• <b>{esc(label)}</b> <code>#{esc(item.get('id', ''))}</code>"
               f" (sejak {esc(item.get('updated_at', '')[:10])})")
        if wa:
            out += f" — <a href='{esc(wa)}'>WA</a>"
    return out


def _handle_listing(text: str) -> str:
    classifier = _get_classifier()
    data = classifier.classify_property(text, source_url="", source_name="Telegram")
    status = str(data.get("status", "TIDAK_RELEVAN")).upper()

    if status not in ("JUAL", "CARI"):
        return ("🤔 Saya tidak yakin ini info jual/cari properti. "
                "Kalau ini memang listing, coba sertakan lokasi, harga, dan tipe propertinya.")

    from models import normalize_listing
    item = normalize_listing(data)
    result = store.save_listing(data, source="telegram_forward")
    listing_id = item["id"]

    label = "PENJUAL" if status == "JUAL" else "PENCARI"
    prefix = "✅ Tersimpan" if result == "new" else "♻️ Diperbarui (sudah ada sebelumnya)"
    reply = (
        f"{prefix} sebagai <b>{label}</b> <code>#{esc(listing_id)}</code>\n"
        f"🏠 {esc(data.get('tipe_properti', '-'))} · 📍 {esc(data.get('lokasi', '-'))}\n"
        f"💰 {format_rupiah(data.get('harga'))} · 🔥 {esc(data.get('kualitas_lead', '-'))}\n"
    )

    # Cari match lawan jenis untuk listing yang baru masuk.
    if status == "JUAL":
        matches = engine.find_matches([item], store.get_pencari())
    else:
        matches = engine.find_matches(store.get_penjual(), [item])

    if matches:
        _get_ai_matcher().enrich_reasons(matches, limit=3)
        store.save_matches(matches)
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
