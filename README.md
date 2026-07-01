# PropMatch — AI Agent Properti Harvey

Sistem otomatis yang mengumpulkan & memahami info properti (penjual dan pencari,
**jual-beli saja — bukan sewa/kontrakan**) di Sidoarjo–Surabaya, mencocokkan
keduanya dengan AI, lalu mengirim laporan ke Telegram dan menampilkannya di
dashboard live. Nilai utamanya: setiap kartu match menampilkan penjual DAN
pencari berdampingan (kontak, postingan, alasan cocok) supaya Anda tinggal
jadi perantara/broker — bukan cuma daftar listing sepihak.

---

## 🧩 Apa saja bagiannya

| Bagian | File | Fungsi |
|---|---|---|
| **Bot Telegram interaktif** | `bot.py`, `api/telegram.py` | Forward/paste info properti → AI klasifikasi → langsung dapat match |
| **Pipeline scraping** | `main.py` | Scrape + klasifikasi + matching + laporan Telegram — manual (tombol dashboard atau `Run workflow` GitHub Actions), TIDAK terjadwal otomatis |
| **Dashboard live** | `api/dashboard.py` + `dashboard/template.html` | Render langsung dari Turso tiap dibuka — data selalu terbaru tanpa redeploy. Filter, update status, Paste & Parse, Match Ulang manual |
| **Otak AI** | `classifier/`, `matcher/` | Klasifikasi Claude Haiku 4.5 (ekstrak data terstruktur) + matching deterministik (skor 0-100) + alasan ditulis ulang AI |
| **Scraper** | `scraper/threads_scraper.py` | Threads (publik, kata kunci semua tipe properti). OLX & Facebook tersedia tapi nonaktif secara default (lihat `ENABLED_SCRAPERS`) |
| **Database** | Turso (libSQL remote) — lihat `db.py` | Sumber kebenaran tunggal, dibaca/ditulis lokal, GitHub Actions, dan semua fungsi Vercel. Tabel `sellers`, `buyers`, `matches` |
| **Landing page** | `landing.html` + `api/submit-lead.py` | Form publik "cari" / "jual" → langsung masuk Turso, instan, tanpa AI (data form sudah terstruktur) |
| **Arsip Google Sheets** | `integrations/google_sheets.py` | Cerminan rapi seluruh data (Penjual, Pencari, Ringkasan) — bisa dibuka & dicek kapan saja tanpa login dashboard |

## 🔎 Scope: jual-beli saja (semua tipe properti)

Sistem ini menerima **semua tipe properti** (rumah, ruko, tanah, apartemen,
kos, gudang, villa), tapi **khusus jual-beli** — BUKAN sewa/kontrakan/kos
per-bulan. Ini ditegakkan lewat prompt classifier AI
(`classifier/claude_classifier.py`): status hanya JUAL/CARI untuk transaksi
beli-jual; apapun yang berbau sewa/kontrakan otomatis `TIDAK_RELEVAN`.

Nilai utama tetap di **sisi permintaan (pembeli)** — siapa yang sedang aktif
mencari, dengan budget & kriteria apa. Sisi penjual sudah melimpah di portal,
sisi pembeli yang langka & berharga.

Atur sumber scraper aktif lewat `ENABLED_SCRAPERS=threads` (atau tambah
`olx`) di `.env`. Facebook Group sengaja tidak diotomasi (lihat komentar di
`scraper/facebook_scraper.py`) — forward manual ke bot Telegram sebagai gantinya.

**Watchdog scraper:** kalau satu sumber (mis. Threads) menghasilkan 0 listing
2x run scraping berturut-turut, sistem otomatis kirim alert Telegram terpisah
(bukan cuma log warning) — tanda kemungkinan diblokir atau struktur halaman
berubah. Lihat `main._check_scraper_watchdog`.

---

## 🚀 Cara Pakai Sehari-hari

### 1. Forward info properti ke bot Telegram
Lihat iklan/postingan jual atau cari rumah di WA grup, Facebook, atau OLX?
**Cukup forward atau copy-paste teksnya ke bot Telegram Anda.** Bot akan:
- membaca & merapikan datanya,
- menyimpannya (otomatis tidak dobel),
- langsung mencarikan pasangan yang cocok beserta skor & alasannya.

Perintah bot:
- Ketik teks listing → otomatis diproses, AI juga menghitung **skor urgensi**
  (0-100) dari kata kunci seperti "BU", "cash", "nego tipis" — lead mendesak
  otomatis naik ke atas di `/top`.
- `/top` → 5 match terbaik (urutan: kecocokan + urgensi), lengkap link
  postingan kedua pihak + tombol **WA siap-klik** (draft pesan sudah terisi,
  tinggal review & kirim manual)
- `/status <id> <status>` → update status lead langsung dari Telegram
  (`new` / `contacted` / `negotiating` / `closed` / `lost`)
- `/matchstatus <id_penjual> <id_pencari> <status>` → tandai satu pasangan match
- `/hapus <id>` → buang listing salah-klasifikasi/duplikat/spam
- `/rekap` atau `/rekap bulan` → rekap performa 7/30 hari terakhir (lead
  baru, closing rate, rata-rata waktu lead→closed)
- `/reminder` → lead "contacted" yang belum di-follow-up >3 hari
- `/stats` → ringkasan jumlah data
- `/help` → bantuan

Dedup lintas-sumber otomatis: listing yang sama diforward manual setelah
sebelumnya kescrape (atau sebaliknya) tetap dikenali sebagai satu lead yang
sama walau teksnya beda kata-kata — dicocokkan lewat nomor kontak, atau
kombinasi tipe+lokasi+harga berdekatan (lihat `store._find_fuzzy_duplicate`).

### 2. Buka dashboard live kapan saja
Dashboard (lihat bagian Deploy) render langsung dari Turso setiap dibuka —
tidak perlu tunggu redeploy. Dari sana Anda bisa:
- Lihat kartu **Top Match**: penjual & pencari berdampingan (kontak, link
  postingan, skor breakdown, alasan cocok).
- Filter status match: Potensial / Sedang Saya Follow-up / Closed / Lost.
- Tombol **🌐 Jalankan Scraping** — memicu GitHub Actions dari jarak jauh.
- Tombol **🎯 Match Ulang** — hitung ulang skor match dari data terkini (instan).
- Tombol **📋 Paste & Parse** — tempel teks listing, AI langsung proses & simpan.
- Update status lead/match langsung dari tabel/kartu.
- Tab **Insight** → **🎯 Motivated Seller Radar**: penjual aktif yang harganya
  ≥15% di bawah rata-rata tipe propertinya sendiri, sinyal kuat "butuh uang
  cepat" walau teks listingnya sendiri tidak bilang begitu.

### 3. Trigger scraping manual (bukan terjadwal)
Scraping SENGAJA tidak berjalan otomatis (lihat `.github/workflows/scrape.yml`)
— jalankan lewat tombol dashboard, atau tab **Actions → Run workflow** di GitHub.

---

## ⚙️ Setup Pertama Kali

1. **Buat database Turso** (gratis, https://turso.tech): `turso db create propmatch`,
   lalu `turso db show propmatch` (URL) dan `turso db tokens create propmatch` (auth token).
   ⚠️ Pakai URL dengan skema **`https://`**, bukan `libsql://` (Turso HTTP client
   di lingkungan ini gagal handshake dengan `libsql://`/`wss://`).

2. **Isi file `.env`** (salin dari `.env.example`):
   - `ANTHROPIC_API_KEY` — dari https://console.anthropic.com/settings/keys (berbayar, ~$0.0016/klasifikasi pakai Haiku 4.5)
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — buat bot lewat @BotFather
   - `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` — dari langkah 1

3. **Install dependency:**
   ```
   pip install -r requirements.txt
   python -m playwright install chromium   # untuk scraper Threads
   ```

4. **Tes koneksi database & buat schema (otomatis):**
   ```
   python db.py
   ```

5. **Jalankan bot interaktif:**
   ```
   python bot.py
   ```

6. **Tes pipeline manual:**
   ```
   python main.py
   ```

---

## 🗄️ Database (Turso / libSQL remote)

Turso adalah **satu-satunya sumber data** — dibaca/ditulis oleh laptop lokal,
GitHub Actions (scraping), dan semua fungsi serverless Vercel sekaligus,
tanpa perlu commit file database ke git. Tiga tabel inti: `sellers`, `buyers`,
`matches`. Setiap listing punya `source` (asal data), `lead_status`
(new/contacted/negotiating/closed/lost), dan `urgency_score` (0-100).

Schema (termasuk migrasi kolom baru) dibuat otomatis & idempoten setiap
koneksi baru dibuka — lihat `db.py`.

---

## 📝 Landing Page (form publik "cari" / "jual")

`landing.html` adalah halaman terpisah dari dashboard — link untuk dibagikan
ke calon klien. `api/submit-lead.py` menulis LANGSUNG ke Turso (sama seperti
`api/parse-text.py`/`api/dashboard.py`) — tidak ada layanan pihak ketiga di
tengah, tidak ada delay menunggu pipeline jalan:

```
landing.html → api/submit-lead.py → Turso (langsung, instan)
```

Tidak butuh setup tambahan apapun di luar env Turso yang sudah diisi di atas.
Data form sudah terstruktur (bukan teks bebas) sehingga tidak perlu panggilan
AI sama sekali — gratis sepenuhnya. Endpoint ini punya honeypot field
tersembunyi (`website`) untuk menyaring bot spam dasar.

---

## 📊 Arsip Google Sheets (cek data kapan saja, format familiar)

Semua data yang pernah masuk (hasil scraping, forward Telegram, landing page)
sudah **selalu tersimpan permanen di Turso** (tidak pernah hilang/tertimpa)
dan bisa dicek kapan saja lewat dashboard. Sebagai tambahan yang lebih
familiar & mudah dibagikan/difilter sendiri, sistem juga bisa menyalin
seluruh data ke satu Google Sheet, dengan 3 tab:

- **Penjual** — Nama, No HP, Jenis Properti, Lokasi, Harga Jual, LT/LB, KT/KM,
  Metode Bayar, Urgensi, Kualitas Lead, Status Lead, Sumber, dst.
- **Pencari** — Nama, No HP, Jenis Properti Dicari, Lokasi Diinginkan,
  Budget Maksimal, dst.
- **Ringkasan** — waktu sinkron terakhir & jumlah data saat ini.

Setiap sinkronisasi **menimpa** isi tab dengan data terkini dari Turso
(bukan menumpuk) — jadi Sheets selalu mencerminkan kondisi terbaru tanpa
duplikat, dengan lead terbaru selalu di baris paling atas.

**Setup sekali saja** (langkah lengkap ada di komentar `.env.example` bagian
"Google Sheets"): buat 1 Google Sheet kosong, buat service account di Google
Cloud Console, share Sheet itu ke email service account, lalu isi
`GOOGLE_SHEETS_ID` + `GOOGLE_SERVICE_ACCOUNT_JSON` di `.env` (lokal) dan di
Secrets GitHub Actions / Environment Variables Vercel.

**Cara sinkron:**
- **Otomatis** setiap kali `python main.py` (pipeline scraping) selesai jalan.
- **Manual kapan saja** lewat tombol **📊 Sinkronkan Google Sheets** di dashboard.

Kalau kredensial belum diisi, fitur ini dilewati diam-diam (tidak mengganggu
scraping/matching) — murni tambahan, bukan bagian yang wajib.

---

## 🌐 Deploy (Vercel + GitHub Actions)

**Dashboard live (Vercel):**
1. `vercel --prod` dari folder ini (atau hubungkan repo GitHub ke Vercel).
2. Set environment variables di Vercel: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`,
   `DASHBOARD_USER`, `DASHBOARD_PASSWORD` (proteksi Basic Auth — dashboard berisi
   data kontak pribadi), `GITHUB_TOKEN` + `GITHUB_REPO` (supaya tombol "Jalankan
   Scraping" bisa memicu GitHub Actions dari dashboard), dan opsional
   `GOOGLE_SHEETS_ID` + `GOOGLE_SERVICE_ACCOUNT_JSON` (supaya tombol "Sinkronkan
   Google Sheets" berfungsi — lihat bagian "Arsip Google Sheets" di atas).
3. Dashboard otomatis live di URL Vercel Anda, render langsung dari Turso.

**Scraping (GitHub Actions, manual only):**
1. Push project ke GitHub.
2. Di **Settings → Secrets and variables → Actions**, tambahkan:
   `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DASHBOARD_URL`,
   `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, dan opsional `GOOGLE_SHEETS_ID` +
   `GOOGLE_SERVICE_ACCOUNT_JSON` (supaya tiap scraping otomatis sinkron ke Sheets).
3. Jalankan lewat tombol dashboard, atau tab **Actions → Run workflow**.
   Tidak ada jadwal otomatis — ini keputusan desain yang disengaja.

---

## 🤖 Bot Selalu-Aktif Tanpa Server (opsional, lanjutan)

`api/telegram.py` + `vercel.json` menyiapkan bot mode webhook di Vercel sehingga
bot aktif 24 jam tanpa perlu `python bot.py` menyala terus. Daftarkan webhook
sekali setelah deploy:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<app>.vercel.app/api/telegram
```

---

## 🔒 Keamanan
- Semua kunci API ada di `.env` (tidak pernah di kode). `.env` & `credentials.json`
  sudah masuk `.gitignore` agar tidak ikut ter-upload ke GitHub.
- Dashboard dilindungi HTTP Basic Auth (`DASHBOARD_USER`/`DASHBOARD_PASSWORD`)
  karena berisi data kontak pribadi penjual/pembeli.
- Data palsu (mock) hanya muncul jika `USE_MOCK_DATA=1` — di produksi tetap `0`.
