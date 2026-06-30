"""
Bot Telegram interaktif (mode polling).

Jalankan: python bot.py
Bot akan terus mendengarkan pesan masuk. Harvey tinggal forward/paste info
properti ke bot, dan langsung dapat balasan klasifikasi + match.

Cocok dijalankan di laptop atau VPS ringan. Untuk versi selalu-aktif tanpa
server, pakai mode webhook (lihat api/telegram.py + deploy ke Vercel).
"""
import logging
import time

import requests

import config
from delivery.handler import process_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bot")

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def send(chat_id, text):
    try:
        requests.post(f"{API}/sendMessage", json={
            "chat_id": chat_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=20)
    except Exception as e:
        logger.error("Gagal mengirim balasan: %s", e)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN belum diset di .env. Bot tidak bisa jalan.")
        return

    logger.info("Bot PropMatch aktif (mode polling). Tekan Ctrl+C untuk berhenti.")
    offset = None
    while True:
        try:
            resp = requests.get(f"{API}/getUpdates", params={
                "timeout": 30, "offset": offset,
            }, timeout=40)
            updates = resp.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("channel_post")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text") or msg.get("caption") or ""
                if not text:
                    send(chat_id, "Kirim teks info properti ya. /help untuk bantuan.")
                    continue
                logger.info("Pesan dari %s: %s", chat_id, text[:60])
                reply = process_message(text)
                send(chat_id, reply)
        except requests.exceptions.RequestException as e:
            logger.warning("Koneksi bermasalah, coba lagi 5 detik: %s", e)
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Bot dihentikan.")
            break
        except Exception as e:
            logger.exception("Error tak terduga di loop bot: %s", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
