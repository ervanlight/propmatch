"""
Notifier Telegram untuk laporan harian.

Mengirim ringkasan ke Harvey: jumlah penjual/pencari baru, lead HOT, dan
Top Match hari ini dalam format yang terbaca dalam 5 detik.
"""
import html
import logging

import requests

import config

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LEN = 4000  # batas aman di bawah 4096


def esc(text) -> str:
    return html.escape(str(text)) if text is not None else ""


class TelegramNotifier:
    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        if not self.bot_token or not self.chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN/CHAT_ID belum diset. Notifikasi nonaktif.")

    def send_message(self, message: str, chat_id: str = None) -> bool:
        target = chat_id or self.chat_id
        if not self.bot_token or not target:
            logger.error("Gagal kirim Telegram: kredensial tidak lengkap.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        ok = True
        for chunk in self._split(message):
            try:
                resp = requests.post(url, json={
                    "chat_id": target,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }, timeout=20)
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                detail = getattr(e.response, "text", "") if hasattr(e, "response") else ""
                logger.error("Gagal kirim Telegram: %s %s", e, detail)
                ok = False
        if ok:
            logger.info("Pesan Telegram terkirim.")
        return ok

    @staticmethod
    def _split(message: str):
        """Potong pesan panjang per baris agar tidak melebihi batas Telegram."""
        if len(message) <= TELEGRAM_MAX_LEN:
            return [message]
        chunks, current = [], ""
        for line in message.split("\n"):
            if len(current) + len(line) + 1 > TELEGRAM_MAX_LEN:
                chunks.append(current)
                current = ""
            current += line + "\n"
        if current:
            chunks.append(current)
        return chunks


def format_rupiah(angka) -> str:
    try:
        angka = int(angka)
    except (TypeError, ValueError):
        return "N/A"
    if angka <= 0:
        return "N/A"
    return "Rp " + f"{angka:,}".replace(",", ".")


def build_daily_report(stats: dict, penjual_baru: int, pencari_baru: int,
                       top_matches: list, dashboard_url: str = "") -> str:
    import datetime
    tanggal = datetime.datetime.now().strftime("%d %B %Y")

    msg = (
        f"📊 <b>LAPORAN PROPERTI HARIAN</b>\n"
        f"<i>{esc(tanggal)} — Sidoarjo &amp; Surabaya</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆕 Penjual baru: <b>{penjual_baru}</b> | Pencari baru: <b>{pencari_baru}</b>\n"
        f"📁 Total aktif: 🏠 {stats.get('total_penjual', 0)} penjual"
        f" · 🔍 {stats.get('total_pencari', 0)} pencari\n"
        f"🔥 Lead HOT: <b>{stats.get('total_hot', 0)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )

    if top_matches:
        msg += f"🎯 <b>TOP MATCH HARI INI</b> ({len(top_matches)} pasangan)\n"
        for i, m in enumerate(top_matches[:5], 1):
            alasan = m.get("alasan_ai") or m.get("alasan", "")
            msg += (
                f"\n<b>#{i} · Skor {m.get('skor_10', 0)}/10</b>\n"
                f"🏠 {esc(m.get('penjual_tipe', ''))} di {esc(m.get('penjual_lokasi', ''))}"
                f" — {format_rupiah(m.get('penjual_harga'))}\n"
                f"🔍 Pencari: {esc(m.get('pencari_lokasi', ''))}"
                f" (budget {format_rupiah(m.get('pencari_budget'))})\n"
                f"💡 <i>{esc(alasan)}</i>\n"
            )
            if m.get("penjual_url"):
                msg += f"🔗 <a href='{esc(m['penjual_url'])}'>Lihat iklan penjual</a>\n"
            if m.get("penjual_kontak"):
                msg += f"📞 {esc(m['penjual_kontak'])}\n"
    else:
        msg += "🎯 Belum ada Top Match baru hari ini.\n"

    if dashboard_url:
        msg += f"\n📈 Dashboard lengkap: {esc(dashboard_url)}"
    return msg


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    TelegramNotifier().send_message("<b>Test</b> Sistem PropMatch berjalan normal.")
