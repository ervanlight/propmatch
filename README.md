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
| **Scraper multi-sumber** | `scraper/` | OLX (penjual), Threads & Facebook (terutama PEMBELI) |
| **Database** | `data/propmatch.db` (SQLite) | Tabel `sellers`, `buyers`, `matches` — anti-duplikat, status lead, urgensi |
| **Landing page** | `landing.html` + `api/submit-lead.py` | Form publik "cari" / "jual" → masuk database via Google Sheets |

## 🔎 Sumber Data (fokus menangkap PEMBELI)

Nilai utama sistem ini ada di **sisi permintaan (pembeli)** — siapa yang sedang
aktif mencari, dengan budget & kriteria apa. Sisi penjual sudah melimpah di
portal, sisi pembeli yang langka & berharga.

| Sumber | File | Menangkap | Kebutuhan |
|---|---|---|---|
| OLX | `scraper/olx_scraper.py` | Penjual (best-effort) | — |
| Threads | `scraper/threads_scraper.py` | Pembeli/penjual via kata kunci publik | `THREADS_KEYWORDS` |
| Facebook Group | `scraper/facebook_scraper.py` | **Pembeli** (postingan "dicari…") | `FB_COOKIE` + `FB_GROUP_IDS` |
| Forward manual ke bot | `bot.py` | Semua (paling andal) | — |

Atur sumber aktif lewat `ENABLED_SCRAPERS=olx,threads,facebook` di `.env`.

**Setup Facebook (sumber pembeli terkaya):**
1. Login ke `mbasic.facebook.com` di browser, buka DevTools → Network → salin
   header `Cookie` dari salah satu request. Tempel ke `FB_COOKIE`.
2. Isi `FB_GROUP_IDS` dengan ID grup jual-beli properti yang Anda ikuti
   (angka di URL grup), dipisah koma.
3. Scraper hanya mengambil postingan bersinyal niat-beli & relevan wilayah.
> Cookie bersifat rahasia — sudah masuk `.gitignore`, simpan sebagai secret.
> Pendekatan ini mengakses data yang memang sudah bisa Anda lihat sebagai anggota grup.

---

## 🚀 Cara Pakai Sehari-hari (paling penting)

### 1. Forward info properti ke bot Telegram
Lihat iklan/postingan jual atau cari properti di WA grup, Facebook, atau OLX?
**Cukup forward atau copy-paste teksnya ke bot Telegram Anda.** Bot akan:
- membaca & merapikan datanya,
- menyimpannya (otomatis tidak dobel),
- langsung mencarikan pasangan yang cocok beserta skor & alasannya.

Perintah bot:
- Ketik teks listing → otomatis diproses, AI juga menghitung **skor urgensi**
  (0-100) dari kata kunci seperti "BU", "cash", "nego tipis" — lead mendesak
  otomatis naik ke atas di `/top`.
- `/top` → 5 match terbaik (urutan: kecocokan + urgensi), lengkap tombol
  **WA siap-klik** (draft pesan sudah terisi, tinggal review & kirim manual)
- `/status <id> <status>` → update status lead langsung dari Telegram
  (`new` / `contacted` / `negotiating` / `closed` / `lost`)
- `/reminder` → lead "contacted" yang belum di-follow-up >3 hari
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
   - `ANTHROPIC_API_KEY` — dari https://console.anthropic.com/settings/keys (berbayar, ~$0.0016/klasifikasi pakai Haiku 4.5)
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

5. **(Kalau upgrade dari versi lama)** migrasikan data JSON lama ke database
   SQLite baru (sekali saja, aman dijalankan berkali-kali):
   ```
   python migrate_json_to_sqlite.py
   ```

---

## 🗄️ Database (SQLite)

Database utama di `data/propmatch.db`, tiga tabel inti: `sellers`, `buyers`,
`matches`. Setiap listing punya `source` (asal data: olx/threads/facebook/
telegram_forward/landing_page), `lead_status` (new/contacted/negotiating/
closed/lost — dikelola lewat `/status`), dan `urgency_score` (0-100, dari
kata kunci mendesak).

File `.db` ikut di-commit oleh GitHub Actions setiap pipeline jalan (sama
seperti file JSON dulu) supaya data persisten antar-run.

---

## 📝 Landing Page (form publik "cari" / "jual")

`landing.html` adalah halaman terpisah dari dashboard — link untuk dibagikan
ke calon klien. Karena form-nya butuh backend (submit data), dan Vercel
serverless **tidak** punya penyimpanan file permanen, alurnya:

```
landing.html → api/submit-lead.py → Google Sheets (kotak surat sementara)
                                          ↓
                            main.py (pipeline harian) menarik lead baru
                                          ↓
                                data/propmatch.db (SQLite)
```

**Setup (sekali saja):**
1. Buat Google Sheet baru (boleh kosong, tab akan dibuat otomatis).
2. Buat Service Account di [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts),
   aktifkan Google Sheets API, download file JSON kredensialnya.
3. Share Google Sheet tadi ke email service account (lihat field `client_email`
   di file JSON) dengan akses **Editor**.
4. Isi `.env`:
   - `GOOGLE_SHEET_URL` — link Sheet tadi.
   - Untuk jalan di laptop: `GOOGLE_CREDENTIALS_FILE=credentials.json` (taruh
     file JSON di folder ini, sudah ter-`.gitignore`).
   - Untuk deploy Vercel: `GOOGLE_CREDENTIALS_JSON` — isi **seluruh konten**
     file JSON tadi sebagai satu baris (lebih aman daripada commit file).
5. Deploy `landing.html` + `api/submit-lead.py` (sudah terdaftar di
   `vercel.json`, akses via `/landing`, `/cari`, atau `/jual`).

Lead yang masuk lewat landing page **tidak butuh panggilan AI sama sekali**
(data form sudah terstruktur) — gratis sepenuhnya.

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
   `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DASHBOARD_URL`.
   Kalau pakai landing page, tambahkan juga `GOOGLE_CREDENTIALS_JSON` dan
   `GOOGLE_SHEET_URL`.
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
