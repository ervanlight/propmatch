# PropMatch — AI Agent Properti Harvey

Sistem otomatis yang mengumpulkan & memahami info properti (penjual dan pencari)
di Sidoarjo–Surabaya, mencocokkan keduanya dengan AI, lalu mengirim laporan ke
Telegram dan menampilkannya di dashboard web.

---

## 🧩 Apa saja bagiannya

| Bagian | File | Fungsi |
|---|---|---|
| **Bot Telegram interaktif** | `bot.py` | Forward/paste info properti → AI klasifikasi → langsung dapat match |
| **Pipeline harian** | `main.py` | Scrape + klasifikasi + matching + laporan pagi otomatis |
| **Dashboard web** | `index.html` | Lihat semua penjual, pencari, & top match (bisa dibuka di HP) |
| **Otak AI** | `classifier/`, `matcher/` | Mengubah teks mentah jadi data & menilai kecocokan |
| **Database** | `data/*.json` | Penyimpanan dengan anti-duplikat & cap waktu |

---

## 🚀 Cara Pakai Sehari-hari (paling penting)

### 1. Forward info properti ke bot Telegram
Lihat iklan/postingan jual atau cari properti di WA grup, Facebook, atau OLX?
**Cukup forward atau copy-paste teksnya ke bot Telegram Anda.** Bot akan:
- membaca & merapikan datanya,
- menyimpannya (otomatis tidak dobel),
- langsung mencarikan pasangan yang cocok beserta skor & alasannya.

Perintah bot:
- Ketik teks listing → otomatis diproses
- `/top` → 5 match terbaik saat ini
- `/stats` → ringkasan jumlah data
- `/help` → bantuan

### 2. Terima laporan pagi otomatis
Setiap pukul 06:00 WIB, sistem mengirim ringkasan harian ke Telegram:
penjual & pencari baru, jumlah lead HOT, dan Top Match untuk langsung ditindaklanjuti.

### 3. Buka dashboard kapan saja
Buka link dashboard (lihat bagian Deploy) untuk melihat & memfilter semua data.

---

## ⚙️ Setup Pertama Kali (sekali saja)

1. **Isi file `.env`** (salin dari `.env.example`):
   - `GEMINI_API_KEY` — dari https://aistudio.google.com/apikey (gratis)
   - `TELEGRAM_BOT_TOKEN` — buat bot lewat @BotFather di Telegram
   - `TELEGRAM_CHAT_ID` — ID chat Anda (kirim pesan ke bot lalu cek
     `https://api.telegram.org/bot<TOKEN>/getUpdates`)

2. **Install dependency** (sekali):
   ```
   pip install -r requirements.txt
   ```

3. **Jalankan bot interaktif:**
   ```
   python bot.py
   ```
   Biarkan jendela ini terbuka selama Anda ingin bot aktif menerima forward.

4. **Tes pipeline harian manual:**
   ```
   python main.py
   ```

---

## 🌐 Membuat Dashboard "Live" (online)

`index.html` adalah file statis — bisa di-host di mana saja:

**Opsi A — cPanel Rumahweb (hosting Anda):**
Upload `index.html` ke folder `public_html` lewat File Manager cPanel. Selesai,
dashboard bisa diakses di domain Anda.

**Opsi B — Vercel / GitHub Pages (gratis & otomatis):**
Hubungkan repo ke Vercel. Setiap pipeline harian meng-update `index.html` dan
otomatis ter-deploy ulang. Isi `DASHBOARD_URL` di `.env`/secrets agar link
muncul di laporan Telegram.

---

## 🔁 Otomasi Harian (GitHub Actions)

File `.github/workflows/daily_scrape.yml` sudah menjadwalkan pipeline tiap pagi.
Yang perlu dilakukan:
1. Push project ini ke repo GitHub.
2. Di **Settings → Secrets and variables → Actions**, tambahkan:
   `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DASHBOARD_URL`.
3. Selesai — laporan akan terkirim otomatis setiap hari. Bisa juga dijalankan
   manual lewat tab **Actions → Run workflow**.

---

## 🤖 Bot Selalu-Aktif Tanpa Server (opsional, lanjutan)

`api/telegram.py` + `vercel.json` menyiapkan bot mode webhook di Vercel sehingga
bot aktif 24 jam tanpa perlu `python bot.py` menyala. Catatan: di mode ini bot
mencocokkan ke snapshot database terakhir; untuk simpan-baca penuh, gunakan
`python bot.py` atau aktifkan Google Sheets.

Daftarkan webhook sekali setelah deploy:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<app>.vercel.app/api/telegram
```

---

## 🔒 Keamanan
- Semua kunci API ada di `.env` (tidak pernah di kode). `.env` & `credentials.json`
  sudah masuk `.gitignore` agar tidak ikut ter-upload ke GitHub.
- Data palsu (mock) hanya muncul jika `USE_MOCK_DATA=1` — di produksi tetap `0`.
