# E-Pelaporan Perjumpaan Kokurikulum — Streamlit

Streamlit web app for co-curricular meeting reports. Replicates the SK Taman Rinting 3 e-pelaporan interface with full CRUD, attendance tracking, statistics dashboard, and PDF generation.

## Features

- **📝 BORANG** — Comprehensive co-curricular meeting report form with:
  - **Maklumat Asas**: Komponen, Pasukan, Tajuk/Kegiatan, Kali Ke, Tarikh (auto-detects Hari), Mula, Akhir, Tempat
  - **Kehadiran Guru Penasihat**: full H/TH list per teacher with auto-calculated attendance %
  - **Kehadiran Murid (Ahli)**: class-filtered list with H/TH per student, bulk Semua/Reset/TH actions, auto-calculated %
  - **Agenda / Tentatif Aktiviti**: Aktiviti Utama + 3 numbered agenda items
  - **Pengisian Elemen**: Elemen Sivik (18 nilai), Elemen K-BAT (6 options), Elemen RIMUP (5 categories), Sisipan PIKEBM (Kemahiran Bahasa Melayu)
  - **Amalan Pendidikan Sivik dalam Kurikulum**: Masa, Nilai, Sub-Nilai (29 contoh aktiviti), Tajuk
  - **Analisis Aktiviti**: Kekuatan, Kelemahan, Cadangan Menangani, Refleksi
  - **Pengesahan**: 3 signature blocks — Disediakan oleh / Disemak oleh / Disahkan oleh, each with Jawatan
  - **Gambar Aktiviti**: 2 image uploads with previews
- **📑 SENARAI** — All submitted reports with filters, search, expandable sections (Maklumat / Aktiviti / Elemen / Sivik / Analisis / Pengesahan / Gambar), PDF download, delete
- **📊 KEHADIRAN** — Statistics dashboard with stat cards, per-team attendance percentages with progress bars, per-student attendance ranking, CSV export
- **🔒 PENTADBIRAN** — **Password-protected** tab to manage school settings, Komponen, Pasukan, Guru, Murid (with bulk CSV import). Default password: `admin123` — change it on first login.

**Design**: Light blue (sky) primary palette with warm orange contrast accent on action buttons. Stat cards have a light-blue → orange accent stripe; submit buttons use the orange accent for high visibility against the blue UI.

**Auto-migration**: If you upgrade from an older version of the app, your existing `epelaporan.db` is automatically extended with the new columns on first run — no data loss.

Storage: **SQLite** (single `epelaporan.db` file). No external services needed.

PDF generation: **ReportLab** — A4 reports with:
- Maklumat Asas (Tajuk, Komponen, Pasukan, Kali Ke, Tarikh/Hari, Masa, Tempat)
- Kehadiran Guru Penasihat (full table + % kehadiran)
- Agenda / Aktiviti
- Pengisian Elemen (Sivik, K-BAT, RIMUP, PIKEBM)
- Amalan Pendidikan Sivik dalam Kurikulum (if filled)
- Analisis Aktiviti (Kekuatan, Kelemahan, Cadangan, Refleksi)
- Kehadiran Murid (full table + % kehadiran)
- Gambar Aktiviti (embedded photos)
- 3-column signature block (Disediakan / Disemak / Disahkan)

---

## Run locally (5 minutes)

### 1. Install Python 3.9+
Make sure you have Python installed. Check with:
```bash
python --version
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`. The database, uploads folder, and PDFs folder are created automatically on first run, seeded with sample data.

---

## Deploy to Streamlit Cloud (free)

### 1. Push to GitHub
Create a new GitHub repo and push these three files:
- `app.py`
- `requirements.txt`
- `README.md`

```bash
git init
git add .
git commit -m "E-Pelaporan Kokurikulum"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git
git push -u origin main
```

### 2. Deploy
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. **New app** → select your repo → main file is `app.py`
4. **Deploy** — takes about a minute

You get a public URL like `https://YOUR-APP.streamlit.app`.

> **Note on Streamlit Cloud storage**: the SQLite database lives on the container's filesystem and persists across reboots, but free-tier apps can have their filesystem reset on redeploys. For mission-critical use, consider:
> - Deploy on your own server (Railway, Render, Fly.io, a VPS)
> - Swap SQLite for a hosted database (Postgres on Supabase/Neon — change the `get_conn()` function and SQL syntax)

---

## Deploy on your own server

### Docker (recommended)
Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build & run:
```bash
docker build -t epelaporan .
docker run -d -p 8501:8501 -v $(pwd)/data:/app/data epelaporan
```

### Plain server (Ubuntu)
```bash
sudo apt update && sudo apt install python3-pip -y
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME
pip3 install -r requirements.txt
nohup streamlit run app.py --server.port=8501 --server.address=0.0.0.0 &
```

Then put nginx in front for HTTPS / a real domain.

---

## File structure

```
your-project/
├── app.py              ← main Streamlit app (everything is here)
├── requirements.txt    ← Python dependencies
├── README.md           ← this file
├── epelaporan.db       ← auto-created SQLite database
├── uploads/            ← uploaded photos (auto-created)
└── pdfs/               ← generated PDF reports (auto-created)
```

---

## How to use

### First run
1. Open the app — sample data loads automatically (Komponen, Pasukan, Guru, Murid)
2. Click the **🔒 PENTADBIRAN** tab → enter default password `admin123` → log in
3. Go to **Tetapan** → scroll down to **🔑 Tukar Kata Laluan Pentadbir** → set your own password
4. Still in **Tetapan**: set your school name, app title, optional logo URL
5. Use the other admin sub-tabs to fill in your real data:
   - **Komponen**: add categories (Unit Beruniform, Persatuan, Sukan, etc.)
   - **Pasukan**: add teams under each category
   - **Guru**: assign advisor teachers to teams
   - **Murid**: add students one-by-one OR upload a CSV with columns `kelas, nama, pasukan`
6. Click **🚪 Log Keluar** when done — the tab re-locks immediately

### Submitting a report
1. **📝 BORANG** tab
2. Pick **Komponen** → Pasukan dropdown enables
3. Pick **Pasukan** → Guru list + student attendance both populate
4. Add advisor teachers using the **+ Tambah** button (they appear as removable chips)
5. Set Kali Ke, Tarikh, Mula, Akhir, Tempat
6. **KEHADIRAN MURID** section:
   - Filter by class with the dropdown
   - Mark each student H (Hadir) or TH (Tidak Hadir)
   - Use bulk buttons: **✓ Semua** (mark filtered as Hadir), **⊗ Reset**, **⛔ Semua TH**
7. Fill activities (Sivik green / KBAT red labels match the original design)
8. Fill Pelapor/Penyemak with positions
9. Upload Gambar 1 and Gambar 2 (optional, JPG/PNG)
10. Click **SIMPAN & JANA PDF** — report saved, attendance logged, PDF generated, download button appears

### Viewing & managing reports
- **📑 SENARAI** → filter by komponen/pasukan/search → expand for details → download PDF or delete
- **📊 KEHADIRAN** → stat cards, per-team percentages with progress bars, per-student attendance ranking, CSV export

---

## Customisation pointers

| Want to change... | Edit |
|---|---|
| School name / logo / title | **⚙ Pentadbiran → Tetapan** in the app |
| Sivik / KBAT / PIKEBM options | `sivik_options`, `kbat_options`, `pikebm_options` lists in `page_borang()` |
| Default times (2:30 / 4:30 PETANG) | `value=` params on `st.text_input` for `mula` and `akhir` |
| PDF layout (fonts, colors, sections) | `generate_pdf()` function |
| Add a new field to the report | 1) Add column to `laporan` table in `init_db()` · 2) Add widget in `page_borang()` · 3) Include in `INSERT` statement · 4) Add to `pdf_data` dict · 5) Show in `page_senarai()` |
| Color scheme | CSS variables at top of `apply_custom_css()` (`--blue`, `--green`, `--red`, etc.) |

---

## Tips

- **Default password**: `admin123` — **change it immediately** on first login via **Pentadbiran → Tetapan → Tukar Kata Laluan**. Passwords are stored as SHA-256 hashes in the database.
- **Forgot password?** Open `epelaporan.db` with any SQLite browser (e.g. [DB Browser for SQLite](https://sqlitebrowser.org/)) → `settings` table → delete the row where `key='admin_password_hash'`, or replace its value with the SHA-256 hash of your new password. The app will restore the default `admin123` hash on next start if missing.
- **Logo not showing**: Use a direct image URL ending in `.png` or `.jpg`. For Google Drive images, use the `https://drive.google.com/uc?export=view&id=FILE_ID` format
- **Backup**: Just copy `epelaporan.db` — it contains everything (including the password hash)
- **Multi-user**: Streamlit doesn't have built-in auth. The Pentadbiran tab uses a session-level password lock (resets when the browser session ends). For per-user logins across all tabs, add [streamlit-authenticator](https://github.com/mkhorasani/Streamlit-Authenticator) or put nginx basic auth in front
- **Data reset**: Delete `epelaporan.db` and restart — fresh start with seed data and default password
- **Mobile**: Streamlit is responsive, but the form is most comfortable on a tablet
- **PDF font for Malay characters**: ReportLab's default Helvetica handles standard Latin characters fine. For custom fonts, register them via `pdfmetrics.registerFont()` in `generate_pdf()`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| `streamlit: command not found` | Use `python -m streamlit run app.py` |
| Port already in use | `streamlit run app.py --server.port=8502` |
| PDF doesn't open | Check the `pdfs/` folder — file is saved there even if download button fails |
| Database locked errors | SQLite supports only one writer at a time; for >5 concurrent users move to PostgreSQL |
| Sample data won't go away | Delete the `epelaporan.db` file, then add your real data in Pentadbiran tab |
