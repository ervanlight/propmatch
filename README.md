# PropMatch — AI Agent Properti Harvey

Sistem otomatis yang mengumpulkan & memahami info properti (penjual dan pencari
**rumah**, jual-beli saja — bukan sewa/kos) di Sidoarjo–Surabaya, mencocokkan
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
| **Scraper** | `scraper/threads_scraper.py` | Threads (publik, kata kunci rumah saja). OLX & Facebook tersedia tapi nonaktif secara default (lihat `ENABLED_SCRAPERS`) |
| **Database** | Turso (libSQL remote) — lihat `db.py` | Sumber kebenaran tunggal, dibaca/ditulis lokal, GitHub Actions, dan semua fungsi Vercel. Tabel `sellers`, `buyers`, `matches` |
| **Landing page** | `landing.html` + `api/submit-lead.py` | Form publik "cari" / "jual" rumah → masuk database via Google Sheets (opsional, butuh setup terpisah) |

## 🔎 Scope: jual-beli RUMAH saja

Sistem ini **khusus rumah** (bukan ruko/tanah/kos/apartemen/gudang/villa) dan
**khusus jual-beli** (bukan sewa/kontrakan). Ini ditegakkan dua lapis:
1. Prompt classifier AI (`classifier/claude_classifier.py`) diinstruksikan menolak selain itu.
2. Safety-net di kode (`models.normalize_listing`) — walau AI keliru, listing di luar scope dipaksa `TIDAK_RELEVAN` sebelum sempat masuk database.

Nilai utama tetap di **sisi permintaan (pembeli)** — siapa yang sedang aktif
mencari rumah, dengan budget & kriteria apa. Sisi penjual sudah melimpah di
portal, sisi pembeli yang langka & berharga.

Atur sumber scraper aktif lewat `ENABLED_SCRAPERS=threads` (atau tambah
`olx`) di `.env`. Facebook Group sengaja tidak diotomasi (lihat komentar di
`scraper/facebook_scraper.py`) — forward manual ke bot Telegram sebagai gantinya.

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
- `/reminder` → lead "contacted" yang belum di-follow-up >3 hari
- `/stats` → ringkasan jumlah data
- `/help` → bantuan

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

## 📝 Landing Page (form publik "cari" / "jual") — opsional

`landing.html` adalah halaman terpisah dari dashboard — link untuk dibagikan
ke calon klien. Karena Vercel serverless tidak punya penyimpanan file
permanen, alurnya lewat Google Sheets sebagai kotak surat sementara:

```
landing.html → api/submit-lead.py → Google Sheets
                                          ↓
                       main.py (pipeline) menarik lead baru → Turso
```

**Setup (sekali saja, opsional — sistem tetap jalan penuh tanpa ini):**
1. Buat Google Sheet baru (boleh kosong, tab akan dibuat otomatis).
2. Buat Service Account di [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts),
   aktifkan Google Sheets API, download file JSON kredensialnya.
3. Share Google Sheet tadi ke email service account (`client_email` di file JSON) dengan akses **Editor**.
4. Isi `.env`: `GOOGLE_SHEET_URL`, lalu `GOOGLE_CREDENTIALS_FILE` (lokal) atau
   `GOOGLE_CREDENTIALS_JSON` (Vercel — isi seluruh konten JSON sebagai satu baris).

---

## 🌐 Deploy (Vercel + GitHub Actions)

**Dashboard live (Vercel):**
1. `vercel --prod` dari folder ini (atau hubungkan repo GitHub ke Vercel).
2. Set environment variables di Vercel: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`,
   `DASHBOARD_USER`, `DASHBOARD_PASSWORD` (proteksi Basic Auth — dashboard berisi
   data kontak pribadi), `GITHUB_TOKEN` + `GITHUB_REPO` (supaya tombol "Jalankan
   Scraping" bisa memicu GitHub Actions dari dashboard).
3. Dashboard otomatis live di URL Vercel Anda, render langsung dari Turso.

**Scraping (GitHub Actions, manual only):**
1. Push project ke GitHub.
2. Di **Settings → Secrets and variables → Actions**, tambahkan:
   `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DASHBOARD_URL`,
   `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`.
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
