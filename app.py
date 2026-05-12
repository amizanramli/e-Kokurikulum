"""
E-PELAPORAN PERJUMPAAN KOKURIKULUM
Streamlit Web App

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Deploy:
    Push to GitHub, deploy on share.streamlit.io
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, time
from pathlib import Path
import json
import io
import base64
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# =========================================================
# CONFIG & DATABASE
# =========================================================
DB_PATH = Path("epelaporan.db")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)

DEFAULT_SETTINGS = {
    "school_name": "NAMA SEKOLAH",
    "app_title": "E-PELAPORAN PERJUMPAAN KOKURIKULUM",
    "school_logo_url": "",
    # SHA-256 of "admin123" — change this in Pentadbiran > Tetapan after first login
    "admin_password_hash": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
}

DEFAULT_KOMPONEN = ["Unit Beruniform", "Persatuan/Kelab", "Sukan/Permainan", "Lain-lain"]

DEFAULT_PASUKAN = [
    ("Unit Beruniform", "Pengakap"),
    ("Unit Beruniform", "Pandu Puteri"),
    ("Persatuan/Kelab", "Kelab Bahasa Inggeris"),
    ("Persatuan/Kelab", "Persatuan Matematik"),
    ("Sukan/Permainan", "Bola Sepak"),
    ("Sukan/Permainan", "Badminton"),
]

DEFAULT_GURU = [
    ("Pengakap", "En. Ahmad bin Ali"),
    ("Pengakap", "Pn. Siti binti Hassan"),
    ("Bola Sepak", "En. Razak bin Ibrahim"),
    ("Kelab Bahasa Inggeris", "Pn. Aminah binti Yusof"),
]

DEFAULT_MURID = [
    ("4 Bestari", "Muhammad Aiman bin Zulkifli", "Pengakap"),
    ("4 Bestari", "Nur Aisyah binti Rahman", "Pengakap"),
    ("5 Cerdas", "Iman bin Hakim", "Bola Sepak"),
    ("5 Cerdas", "Sarah binti Daniel", "Kelab Bahasa Inggeris"),
]


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS komponen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT UNIQUE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS pasukan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        komponen TEXT,
        nama TEXT,
        UNIQUE(komponen, nama)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS guru (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pasukan TEXT,
        nama TEXT,
        UNIQUE(pasukan, nama)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS murid (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kelas TEXT,
        nama TEXT,
        pasukan TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS laporan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        komponen TEXT,
        pasukan TEXT,
        guru_hadir TEXT,
        kali_ke INTEGER,
        tarikh TEXT,
        mula TEXT,
        akhir TEXT,
        tempat TEXT,
        jumlah_hadir INTEGER,
        jumlah_murid INTEGER,
        elemen_sivik TEXT,
        elemen_kbat TEXT,
        sisipan_pikebm TEXT,
        aktiviti_utama TEXT,
        aktiviti_1 TEXT,
        aktiviti_2 TEXT,
        aktiviti_3 TEXT,
        refleksi TEXT,
        pelapor TEXT,
        jawatan_pelapor TEXT,
        penyemak TEXT,
        jawatan_penyemak TEXT,
        gambar_1_path TEXT,
        gambar_2_path TEXT,
        pdf_path TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS kehadiran (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        laporan_id INTEGER,
        tarikh TEXT,
        pasukan TEXT,
        kelas TEXT,
        nama_murid TEXT,
        status TEXT,
        FOREIGN KEY(laporan_id) REFERENCES laporan(id)
    )""")

    # Seed defaults if empty
    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    if c.execute("SELECT COUNT(*) FROM komponen").fetchone()[0] == 0:
        for k in DEFAULT_KOMPONEN:
            c.execute("INSERT INTO komponen (nama) VALUES (?)", (k,))
    if c.execute("SELECT COUNT(*) FROM pasukan").fetchone()[0] == 0:
        c.executemany("INSERT INTO pasukan (komponen, nama) VALUES (?, ?)", DEFAULT_PASUKAN)
    if c.execute("SELECT COUNT(*) FROM guru").fetchone()[0] == 0:
        c.executemany("INSERT INTO guru (pasukan, nama) VALUES (?, ?)", DEFAULT_GURU)
    if c.execute("SELECT COUNT(*) FROM murid").fetchone()[0] == 0:
        c.executemany("INSERT INTO murid (kelas, nama, pasukan) VALUES (?, ?, ?)", DEFAULT_MURID)

    conn.commit()
    conn.close()


def get_setting(key, default=""):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# ===== Password helpers =====
def hash_password(password: str) -> str:
    """SHA-256 hash of the password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_admin_password(password: str) -> bool:
    """Check supplied password against stored hash."""
    stored = get_setting("admin_password_hash", "")
    return bool(stored) and hash_password(password) == stored


def set_admin_password(new_password: str) -> None:
    set_setting("admin_password_hash", hash_password(new_password))


def get_komponen():
    conn = get_conn()
    rows = [r[0] for r in conn.execute("SELECT nama FROM komponen ORDER BY nama").fetchall()]
    conn.close()
    return rows


def get_pasukan(komponen=None):
    conn = get_conn()
    if komponen:
        rows = [r[0] for r in conn.execute(
            "SELECT nama FROM pasukan WHERE komponen=? ORDER BY nama", (komponen,)).fetchall()]
    else:
        rows = [r[0] for r in conn.execute("SELECT nama FROM pasukan ORDER BY nama").fetchall()]
    conn.close()
    return rows


def get_guru(pasukan=None):
    conn = get_conn()
    if pasukan:
        rows = [r[0] for r in conn.execute(
            "SELECT nama FROM guru WHERE pasukan=? ORDER BY nama", (pasukan,)).fetchall()]
    else:
        rows = [r[0] for r in conn.execute("SELECT nama FROM guru ORDER BY nama").fetchall()]
    conn.close()
    return rows


def get_murid(pasukan=None):
    conn = get_conn()
    if pasukan:
        df = pd.read_sql_query(
            "SELECT id, kelas, nama, pasukan FROM murid WHERE pasukan=? ORDER BY kelas, nama",
            conn, params=(pasukan,))
    else:
        df = pd.read_sql_query("SELECT id, kelas, nama, pasukan FROM murid ORDER BY kelas, nama", conn)
    conn.close()
    return df


def get_all_reports():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM laporan ORDER BY id DESC", conn)
    conn.close()
    return df


def get_kehadiran_log():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM kehadiran", conn)
    conn.close()
    return df


# =========================================================
# PDF GENERATION
# =========================================================
def generate_pdf(laporan_id: int, data: dict, attendance: list, gambar_paths: list) -> str:
    """Generate a PDF report and return its path."""
    pdf_path = PDF_DIR / f"LPR-{laporan_id:06d}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm
    )

    styles = getSampleStyleSheet()
    BLUE = colors.HexColor("#38bdf8")        # light blue accent
    BLUE_DARK = colors.HexColor("#0284c7")   # darker for headings (contrast)

    title_style = ParagraphStyle(
        "T", parent=styles["Title"], textColor=BLUE_DARK,
        fontSize=14, alignment=TA_CENTER, spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "S", parent=styles["Normal"], textColor=colors.grey,
        fontSize=10, alignment=TA_CENTER, spaceAfter=16
    )
    h3_style = ParagraphStyle(
        "H3", parent=styles["Heading3"], textColor=BLUE_DARK,
        fontSize=11, spaceBefore=14, spaceAfter=6,
        borderPadding=0, borderWidth=0
    )
    body_style = ParagraphStyle("B", parent=styles["Normal"], fontSize=9, leading=12)

    story = []

    school_name = get_setting("school_name")
    app_title = get_setting("app_title")

    story.append(Paragraph(app_title, title_style))
    story.append(Paragraph(school_name, subtitle_style))

    def section(title):
        story.append(Paragraph(f"<b>{title}</b>", h3_style))
        story.append(Spacer(1, 4))

    def info_table(rows):
        t = Table(rows, colWidths=[5 * cm, 11 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#495057")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ]))
        return t

    section("MAKLUMAT ASAS")
    tarikh_str = data.get("tarikh", "")
    if tarikh_str:
        try:
            tarikh_str = datetime.fromisoformat(tarikh_str).strftime("%d/%m/%Y")
        except Exception:
            pass
    story.append(info_table([
        ["Komponen", data.get("komponen", "")],
        ["Pasukan", data.get("pasukan", "")],
        ["Guru Penasihat Hadir", data.get("guru_hadir", "")],
        ["Kali Ke / Tarikh", f"{data.get('kali_ke', '')}  |  {tarikh_str}"],
        ["Masa", f"{data.get('mula', '')} – {data.get('akhir', '')}"],
        ["Tempat", data.get("tempat", "")],
        ["Kehadiran Murid", f"{data.get('jumlah_hadir', 0)} / {data.get('jumlah_murid', 0)}"],
    ]))

    section("PENGISIAN AKTIVITI")
    story.append(info_table([
        ["Elemen Pend. Sivik", data.get("elemen_sivik", "")],
        ["Elemen KBAT", data.get("elemen_kbat", "")],
        ["Sisipan PIKEBM", data.get("sisipan_pikebm", "")],
        ["Aktiviti Utama", Paragraph(data.get("aktiviti_utama", "") or "", body_style)],
        ["Aktiviti 1", data.get("aktiviti_1", "")],
        ["Aktiviti 2", data.get("aktiviti_2", "")],
        ["Aktiviti 3", data.get("aktiviti_3", "")],
        ["Refleksi", Paragraph(data.get("refleksi", "") or "", body_style)],
    ]))

    section("KEHADIRAN MURID")
    att_rows = [["Bil", "Nama", "Kelas", "Status"]]
    for i, a in enumerate(attendance, 1):
        att_rows.append([str(i), a["nama"], a["kelas"], "Hadir" if a["status"] == "H" else "Tidak Hadir"])
    att_table = Table(att_rows, colWidths=[1.2 * cm, 8 * cm, 3 * cm, 3.8 * cm])
    att_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (3, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dee2e6")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(att_table)

    # Images
    valid_images = [p for p in gambar_paths if p and Path(p).exists()]
    if valid_images:
        story.append(PageBreak())
        section("GAMBAR AKTIVITI")
        for p in valid_images:
            try:
                story.append(RLImage(str(p), width=14 * cm, height=10 * cm, kind="proportional"))
                story.append(Spacer(1, 10))
            except Exception:
                pass

    # Signatures
    story.append(Spacer(1, 30))
    sig_table = Table([
        ["_______________________", "_______________________"],
        [data.get("pelapor", ""), data.get("penyemak", "")],
        [f"{data.get('jawatan_pelapor', '')} (Pelapor)", f"{data.get('jawatan_penyemak', '')} (Penyemak)"],
    ], colWidths=[8 * cm, 8 * cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.grey),
    ]))
    story.append(sig_table)

    doc.build(story)
    return str(pdf_path)


# =========================================================
# STYLING
# =========================================================
def apply_custom_css():
    st.markdown("""
    <style>
        /* Root vars — light blue primary with warm contrast accents */
        :root {
            --blue: #38bdf8;            /* sky-400 — light blue primary */
            --blue-dark: #0284c7;       /* sky-600 — for hover / text contrast */
            --blue-deep: #075985;       /* sky-800 — for headings */
            --blue-soft: #e0f2fe;       /* sky-100 — backgrounds */
            --blue-mist: #f0f9ff;       /* sky-50 — very light surfaces */
            --accent: #f97316;          /* orange-500 — contrast accent */
            --accent-soft: #fff7ed;     /* orange-50 */
            --green: #10b981;           /* emerald-500 */
            --red: #ef4444;             /* red-500 */
            --yellow: #f59e0b;          /* amber-500 */
            --cyan: #06b6d4;            /* cyan-500 */
            --ink: #0f172a;             /* slate-900 */
            --ink-soft: #334155;        /* slate-700 */
            --ink-faint: #64748b;       /* slate-500 */
            --line: #e2e8f0;            /* slate-200 */
            --bg: #f8fafc;              /* slate-50 */
        }

        /* Page background */
        .stApp {
            background: var(--bg);
        }

        /* Container width */
        .main .block-container {
            max-width: 1050px;
            padding-top: 1.5rem;
            padding-bottom: 4rem;
        }

        /* Header */
        .app-header {
            text-align: center;
            padding: 16px 20px 24px;
        }
        .logo-fallback {
            width: 88px; height: 88px;
            margin: 0 auto 8px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--blue), var(--blue-deep));
            color: #fff;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 22px; letter-spacing: 1px;
            box-shadow: 0 8px 20px rgba(56, 189, 248, 0.35);
        }
        .app-header h1 {
            color: var(--blue-deep);
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin: 6px 0 2px;
        }
        .app-header h2 {
            color: var(--ink-faint);
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.8px;
            margin: 0;
        }

        /* Card-style section */
        .section-title {
            color: var(--blue-deep);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 1px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--blue);
            margin: 14px 0 12px;
            text-transform: uppercase;
            position: relative;
        }
        .section-title::before {
            content: "";
            position: absolute;
            left: 0; bottom: -2px;
            width: 40px; height: 2px;
            background: var(--accent);
        }
        .sub-section-title {
            color: var(--blue-dark);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.8px;
            margin: 6px 0 8px;
            text-transform: uppercase;
        }

        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background: #fff;
            padding: 8px;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .stTabs [data-baseweb="tab"] {
            height: 44px;
            padding: 0 22px;
            border-radius: 8px;
            font-weight: 600;
            color: var(--ink-faint);
            background: transparent;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, var(--blue), var(--blue-dark)) !important;
            color: #fff !important;
            box-shadow: 0 2px 8px rgba(56, 189, 248, 0.4);
        }

        /* Color-coded labels */
        .label-green {
            color: var(--green);
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
        }
        .label-red {
            color: var(--red);
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
        }
        .label-accent {
            color: var(--accent);
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
        }

        /* Guru advisor sub-card */
        .guru-card {
            background: var(--blue-soft);
            border: 1px solid var(--blue);
            border-radius: 10px;
            padding: 14px 16px;
            margin: 6px 0 16px;
            box-shadow: 0 2px 6px rgba(56, 189, 248, 0.1);
        }

        /* Submit button (primary) — uses accent (orange) for high contrast against light blue UI */
        div.stButton > button[kind="primary"] {
            width: 100%;
            background: var(--accent);
            color: #fff;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 12px;
            font-size: 16px;
            border: none;
            border-radius: 8px;
            text-transform: uppercase;
            transition: all 0.15s ease;
            box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
        }
        div.stButton > button[kind="primary"]:hover {
            background: #ea580c;
            box-shadow: 0 6px 16px rgba(249, 115, 22, 0.4);
            transform: translateY(-1px);
        }

        /* Secondary buttons — light blue tint */
        div.stButton > button[kind="secondary"] {
            border: 1px solid var(--blue);
            color: var(--blue-dark);
            background: #fff;
            font-weight: 600;
        }
        div.stButton > button[kind="secondary"]:hover {
            background: var(--blue-soft);
            border-color: var(--blue-dark);
            color: var(--blue-deep);
        }

        /* Stat cards */
        .stat-card {
            background: #fff;
            border: 1px solid var(--line);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
        }
        .stat-card .label {
            font-size: 11px;
            color: var(--ink-faint);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .stat-card .val {
            font-size: 28px;
            font-weight: 700;
            color: var(--blue-deep);
            line-height: 1.2;
        }

        /* Hide footer */
        footer { visibility: hidden; }
        #MainMenu { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# STREAMLIT STATE HELPERS
# =========================================================
def init_session_state():
    defaults = {
        "guru_chips": [],
        "attendance": {},  # {murid_id: 'H'|'TH'|''}
        "last_pasukan": None,
        "kelas_filter": "-- Papar Semua Kelas --",
        "form_reset_counter": 0,
        "admin_authenticated": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_form_state():
    st.session_state.guru_chips = []
    st.session_state.attendance = {}
    st.session_state.last_pasukan = None
    st.session_state.kelas_filter = "-- Papar Semua Kelas --"
    st.session_state.form_reset_counter += 1


# =========================================================
# PAGE: BORANG
# =========================================================
def page_borang():
    st.markdown('<div class="section-title">MAKLUMAT ASAS</div>', unsafe_allow_html=True)

    # Komponen → Pasukan cascading
    komponen_list = [""] + get_komponen()
    komponen = st.selectbox(
        "KOMPONEN",
        komponen_list,
        format_func=lambda x: "Pilih Komponen..." if x == "" else x,
        key=f"komponen_{st.session_state.form_reset_counter}"
    )

    pasukan_options = [""] + get_pasukan(komponen) if komponen else [""]
    pasukan = st.selectbox(
        "PASUKAN",
        pasukan_options,
        format_func=lambda x: ("Pilih Pasukan..." if komponen else "Pilih Komponen Dahulu") if x == "" else x,
        disabled=not komponen,
        key=f"pasukan_{st.session_state.form_reset_counter}"
    )

    # If pasukan changed, reset attendance & chips
    if pasukan != st.session_state.last_pasukan:
        st.session_state.last_pasukan = pasukan
        st.session_state.guru_chips = []
        if pasukan:
            murid_df = get_murid(pasukan)
            st.session_state.attendance = {int(r.id): "" for r in murid_df.itertuples()}
        else:
            st.session_state.attendance = {}

    # GURU PENASIHAT sub-card
    st.markdown('<div class="guru-card">', unsafe_allow_html=True)
    st.markdown('<div class="sub-section-title">KEHADIRAN GURU PENASIHAT</div>', unsafe_allow_html=True)

    guru_list = get_guru(pasukan) if pasukan else []
    available_guru = [g for g in guru_list if g not in st.session_state.guru_chips]

    col_g1, col_g2 = st.columns([4, 1])
    with col_g1:
        guru_pick = st.selectbox(
            "Pilih Guru",
            [""] + available_guru,
            format_func=lambda x: "Pilih Pasukan Dahulu..." if not pasukan else ("-- Pilih Guru --" if x == "" else x),
            disabled=not pasukan,
            label_visibility="collapsed",
            key=f"guru_pick_{st.session_state.form_reset_counter}"
        )
    with col_g2:
        if st.button("+ Tambah", disabled=not guru_pick, use_container_width=True):
            if guru_pick and guru_pick not in st.session_state.guru_chips:
                st.session_state.guru_chips.append(guru_pick)
                st.rerun()

    if st.session_state.guru_chips:
        chip_cols = st.columns(min(len(st.session_state.guru_chips), 4))
        for i, g in enumerate(st.session_state.guru_chips):
            with chip_cols[i % 4]:
                if st.button(f"✕ {g}", key=f"chip_{i}", help="Klik untuk buang"):
                    st.session_state.guru_chips.remove(g)
                    st.rerun()
    else:
        st.caption("_Tiada guru dipilih._")
    st.markdown('</div>', unsafe_allow_html=True)

    # Kali Ke / Tarikh / Mula / Akhir / Tempat
    col1, col2 = st.columns(2)
    with col1:
        kali_ke = st.selectbox("KALI KE", list(range(1, 31)), key=f"kali_ke_{st.session_state.form_reset_counter}")
    with col2:
        tarikh = st.date_input("TARIKH", value=date.today(), format="DD/MM/YYYY",
                               key=f"tarikh_{st.session_state.form_reset_counter}")

    col3, col4 = st.columns(2)
    with col3:
        mula = st.text_input("MULA", value="2:30 PETANG", key=f"mula_{st.session_state.form_reset_counter}")
    with col4:
        akhir = st.text_input("AKHIR", value="4:30 PETANG", key=f"akhir_{st.session_state.form_reset_counter}")

    tempat = st.text_input("TEMPAT", placeholder="Contoh: Dewan sekolah",
                           key=f"tempat_{st.session_state.form_reset_counter}")

    # ========== KEHADIRAN MURID ==========
    st.markdown('<div class="section-title">KEHADIRAN MURID</div>', unsafe_allow_html=True)

    if not pasukan:
        st.info("Sila pilih Pasukan untuk papar nama murid.")
    else:
        murid_df = get_murid(pasukan)
        if murid_df.empty:
            st.warning("Tiada murid berdaftar untuk pasukan ini. Tambah dari tab **Pentadbiran**.")
        else:
            # Toolbar
            tcol1, tcol2, tcol3, tcol4, tcol5 = st.columns([2, 1, 1, 1, 1])
            kelas_options = ["-- Papar Semua Kelas --"] + sorted(murid_df["kelas"].unique().tolist())
            with tcol1:
                kelas_filter = st.selectbox("Filter Kelas", kelas_options,
                                           label_visibility="collapsed",
                                           key=f"kelas_filter_{st.session_state.form_reset_counter}")
            with tcol2:
                if st.button("✓ Semua", use_container_width=True):
                    for mid in st.session_state.attendance:
                        m_row = murid_df[murid_df["id"] == mid]
                        if not m_row.empty:
                            if kelas_filter == "-- Papar Semua Kelas --" or m_row.iloc[0]["kelas"] == kelas_filter:
                                st.session_state.attendance[mid] = "H"
                    st.rerun()
            with tcol3:
                if st.button("⊗ Reset", use_container_width=True):
                    for mid in st.session_state.attendance:
                        m_row = murid_df[murid_df["id"] == mid]
                        if not m_row.empty:
                            if kelas_filter == "-- Papar Semua Kelas --" or m_row.iloc[0]["kelas"] == kelas_filter:
                                st.session_state.attendance[mid] = ""
                    st.rerun()
            with tcol4:
                if st.button("⛔ Semua TH", use_container_width=True):
                    for mid in st.session_state.attendance:
                        m_row = murid_df[murid_df["id"] == mid]
                        if not m_row.empty:
                            if kelas_filter == "-- Papar Semua Kelas --" or m_row.iloc[0]["kelas"] == kelas_filter:
                                st.session_state.attendance[mid] = "TH"
                    st.rerun()
            with tcol5:
                pass  # PDF button placeholder — full PDF is generated on submit

            # Filtered display
            display_df = murid_df if kelas_filter == "-- Papar Semua Kelas --" else murid_df[murid_df["kelas"] == kelas_filter]

            if display_df.empty:
                st.caption("_Tiada murid untuk kelas ini._")
            else:
                # Render attendance rows
                for idx, row in display_df.reset_index(drop=True).iterrows():
                    mid = int(row["id"])
                    current = st.session_state.attendance.get(mid, "")
                    rcol1, rcol2, rcol3 = st.columns([5, 1, 1])
                    with rcol1:
                        st.markdown(
                            f"<div style='padding:6px 0'>"
                            f"<span style='color:#6c757d;font-size:13px;font-weight:600;margin-right:8px'>{idx+1}.</span>"
                            f"<span>{row['nama']}</span>"
                            f"<small style='color:#6c757d;margin-left:8px'>{row['kelas']}</small>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    with rcol2:
                        h_label = "✓ H" if current == "H" else "H"
                        if st.button(h_label, key=f"h_{mid}", use_container_width=True,
                                    type="primary" if current == "H" else "secondary"):
                            st.session_state.attendance[mid] = "" if current == "H" else "H"
                            st.rerun()
                    with rcol3:
                        th_label = "✓ TH" if current == "TH" else "TH"
                        if st.button(th_label, key=f"th_{mid}", use_container_width=True,
                                    type="primary" if current == "TH" else "secondary"):
                            st.session_state.attendance[mid] = "" if current == "TH" else "TH"
                            st.rerun()

            hadir_count = sum(1 for v in st.session_state.attendance.values() if v == "H")
            total_count = len(st.session_state.attendance)
            st.markdown(
                f"<div style='text-align:right;font-weight:700;color:#495057;margin-top:8px'>"
                f"<span style='color:var(--blue-deep);font-size:18px'>{hadir_count}</span> / {total_count} Hadir</div>",
                unsafe_allow_html=True
            )

    # ========== PENGISIAN AKTIVITI ==========
    st.markdown('<div class="section-title">PENGISIAN AKTIVITI</div>', unsafe_allow_html=True)

    sivik_options = ["", "Kasih Sayang", "Kegembiraan", "Hormat-menghormati", "Bertanggungjawab", "Berterima Kasih"]
    kbat_options = ["", "Mengaplikasi", "Menganalisis", "Menilai", "Mencipta"]
    pikebm_options = ["Tiada", "Patriotisme", "Penyayang", "Keusahawanan", "Kelestarian Alam Sekitar"]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="label-green">ELEMEN PEND. SIVIK</div>', unsafe_allow_html=True)
        elemen_sivik = st.selectbox("", sivik_options,
            format_func=lambda x: "-- Pilih --" if x == "" else x,
            label_visibility="collapsed",
            key=f"sivik_{st.session_state.form_reset_counter}")
    with col_b:
        st.markdown('<div class="label-red">ELEMEN KBAT</div>', unsafe_allow_html=True)
        elemen_kbat = st.selectbox("", kbat_options,
            format_func=lambda x: "-- Pilih --" if x == "" else x,
            label_visibility="collapsed",
            key=f"kbat_{st.session_state.form_reset_counter}")

    sisipan = st.selectbox("SISIPAN PIKEBM", pikebm_options,
                           key=f"pikebm_{st.session_state.form_reset_counter}")
    aktiviti_utama = st.text_area("AKTIVITI UTAMA", placeholder="Aktiviti utama perjumpaan...",
                                  key=f"au_{st.session_state.form_reset_counter}")
    aktiviti_1 = st.text_input("AKTIVITI 1", key=f"a1_{st.session_state.form_reset_counter}")
    aktiviti_2 = st.text_input("AKTIVITI 2", key=f"a2_{st.session_state.form_reset_counter}")
    aktiviti_3 = st.text_input("AKTIVITI 3", key=f"a3_{st.session_state.form_reset_counter}")
    refleksi = st.text_area("REFLEKSI", placeholder="Refleksi perjumpaan...",
                            key=f"rf_{st.session_state.form_reset_counter}")

    # ========== PENGESAHAN & GAMBAR ==========
    st.markdown('<div class="section-title">PENGESAHAN & GAMBAR</div>', unsafe_allow_html=True)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        pelapor = st.text_input("PELAPOR", key=f"pl_{st.session_state.form_reset_counter}")
    with col_p2:
        jawatan_pelapor = st.text_input("JAWATAN PELAPOR", placeholder="Contoh: Guru Penasihat",
                                        key=f"jp_{st.session_state.form_reset_counter}")

    col_p3, col_p4 = st.columns(2)
    with col_p3:
        penyemak = st.text_input("PENYEMAK", key=f"ps_{st.session_state.form_reset_counter}")
    with col_p4:
        jawatan_penyemak = st.text_input("JAWATAN PENYEMAK", placeholder="Contoh: Guru Besar",
                                         key=f"jpn_{st.session_state.form_reset_counter}")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        gambar_1 = st.file_uploader("Gambar 1", type=["png", "jpg", "jpeg"],
                                    key=f"g1_{st.session_state.form_reset_counter}")
        if gambar_1:
            st.image(gambar_1, use_container_width=True)
    with col_g2:
        gambar_2 = st.file_uploader("Gambar 2", type=["png", "jpg", "jpeg"],
                                    key=f"g2_{st.session_state.form_reset_counter}")
        if gambar_2:
            st.image(gambar_2, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ========== SUBMIT ==========
    if st.button("SIMPAN & JANA PDF", type="primary", use_container_width=True):
        if not komponen or not pasukan:
            st.error("Sila lengkapkan Komponen dan Pasukan.")
            return

        # Save images
        gambar_1_path = ""
        gambar_2_path = ""
        ts_tag = datetime.now().strftime("%Y%m%d-%H%M%S")
        if gambar_1:
            ext = Path(gambar_1.name).suffix
            gambar_1_path = str(UPLOAD_DIR / f"{ts_tag}-1{ext}")
            with open(gambar_1_path, "wb") as f:
                f.write(gambar_1.getbuffer())
        if gambar_2:
            ext = Path(gambar_2.name).suffix
            gambar_2_path = str(UPLOAD_DIR / f"{ts_tag}-2{ext}")
            with open(gambar_2_path, "wb") as f:
                f.write(gambar_2.getbuffer())

        # Build attendance list
        murid_df = get_murid(pasukan)
        attendance_list = []
        for _, r in murid_df.iterrows():
            mid = int(r["id"])
            status = st.session_state.attendance.get(mid, "")
            attendance_list.append({"nama": r["nama"], "kelas": r["kelas"], "status": status})

        jumlah_hadir = sum(1 for a in attendance_list if a["status"] == "H")
        jumlah_murid = len(attendance_list)

        # Insert report
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT INTO laporan (
            timestamp, komponen, pasukan, guru_hadir, kali_ke, tarikh, mula, akhir, tempat,
            jumlah_hadir, jumlah_murid,
            elemen_sivik, elemen_kbat, sisipan_pikebm,
            aktiviti_utama, aktiviti_1, aktiviti_2, aktiviti_3, refleksi,
            pelapor, jawatan_pelapor, penyemak, jawatan_penyemak,
            gambar_1_path, gambar_2_path, pdf_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            datetime.now().isoformat(), komponen, pasukan,
            ", ".join(st.session_state.guru_chips),
            kali_ke, tarikh.isoformat(), mula, akhir, tempat,
            jumlah_hadir, jumlah_murid,
            elemen_sivik, elemen_kbat, sisipan,
            aktiviti_utama, aktiviti_1, aktiviti_2, aktiviti_3, refleksi,
            pelapor, jawatan_pelapor, penyemak, jawatan_penyemak,
            gambar_1_path, gambar_2_path, ""
        ))
        laporan_id = cur.lastrowid

        # Insert attendance rows
        for a in attendance_list:
            cur.execute("""INSERT INTO kehadiran (laporan_id, tarikh, pasukan, kelas, nama_murid, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (laporan_id, tarikh.isoformat(), pasukan, a["kelas"], a["nama"], a["status"]))
        conn.commit()

        # Generate PDF
        pdf_data = {
            "komponen": komponen, "pasukan": pasukan,
            "guru_hadir": ", ".join(st.session_state.guru_chips),
            "kali_ke": kali_ke, "tarikh": tarikh.isoformat(),
            "mula": mula, "akhir": akhir, "tempat": tempat,
            "jumlah_hadir": jumlah_hadir, "jumlah_murid": jumlah_murid,
            "elemen_sivik": elemen_sivik, "elemen_kbat": elemen_kbat,
            "sisipan_pikebm": sisipan,
            "aktiviti_utama": aktiviti_utama, "aktiviti_1": aktiviti_1,
            "aktiviti_2": aktiviti_2, "aktiviti_3": aktiviti_3,
            "refleksi": refleksi,
            "pelapor": pelapor, "jawatan_pelapor": jawatan_pelapor,
            "penyemak": penyemak, "jawatan_penyemak": jawatan_penyemak,
        }
        pdf_path = generate_pdf(laporan_id, pdf_data, attendance_list,
                                [gambar_1_path, gambar_2_path])
        cur.execute("UPDATE laporan SET pdf_path=? WHERE id=?", (pdf_path, laporan_id))
        conn.commit()
        conn.close()

        st.success(f"✅ Laporan #{laporan_id} berjaya disimpan. PDF dijana.")

        # Offer download
        with open(pdf_path, "rb") as f:
            st.download_button(
                "⬇ Muat Turun PDF",
                f.read(),
                file_name=f"LPR-{laporan_id:06d}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        reset_form_state()


# =========================================================
# PAGE: SENARAI
# =========================================================
def page_senarai():
    st.markdown('<div class="section-title">SENARAI LAPORAN</div>', unsafe_allow_html=True)

    df = get_all_reports()
    if df.empty:
        st.info("Tiada laporan dihantar lagi.")
        return

    # Filter controls
    col1, col2, col3 = st.columns(3)
    with col1:
        komp_filter = st.selectbox("Filter Komponen", ["Semua"] + sorted(df["komponen"].dropna().unique().tolist()))
    with col2:
        pasukan_filter = st.selectbox("Filter Pasukan", ["Semua"] + sorted(df["pasukan"].dropna().unique().tolist()))
    with col3:
        search = st.text_input("Carian", placeholder="Cari pelapor, tempat, dll...")

    filtered = df.copy()
    if komp_filter != "Semua":
        filtered = filtered[filtered["komponen"] == komp_filter]
    if pasukan_filter != "Semua":
        filtered = filtered[filtered["pasukan"] == pasukan_filter]
    if search:
        s = search.lower()
        mask = filtered.apply(lambda r: any(s in str(v).lower() for v in r.values), axis=1)
        filtered = filtered[mask]

    st.caption(f"Memaparkan **{len(filtered)}** daripada {len(df)} laporan")

    for _, r in filtered.iterrows():
        try:
            tarikh_disp = datetime.fromisoformat(r["tarikh"]).strftime("%d/%m/%Y") if r["tarikh"] else "-"
        except Exception:
            tarikh_disp = r["tarikh"] or "-"

        with st.expander(f"📋 **{r['pasukan']}** · {tarikh_disp} · Kali ke-{r['kali_ke']} · {r['jumlah_hadir']}/{r['jumlah_murid']} hadir"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Komponen:** {r['komponen']}")
                st.markdown(f"**Guru Hadir:** {r['guru_hadir'] or '-'}")
                st.markdown(f"**Masa:** {r['mula']} – {r['akhir']}")
                st.markdown(f"**Tempat:** {r['tempat'] or '-'}")
                st.markdown(f"**Elemen Sivik:** {r['elemen_sivik'] or '-'}")
                st.markdown(f"**Elemen KBAT:** {r['elemen_kbat'] or '-'}")
                st.markdown(f"**PIKEBM:** {r['sisipan_pikebm'] or '-'}")
            with c2:
                st.markdown(f"**Aktiviti Utama:**\n{r['aktiviti_utama'] or '-'}")
                st.markdown(f"**Aktiviti 1:** {r['aktiviti_1'] or '-'}")
                st.markdown(f"**Aktiviti 2:** {r['aktiviti_2'] or '-'}")
                st.markdown(f"**Aktiviti 3:** {r['aktiviti_3'] or '-'}")
                st.markdown(f"**Refleksi:** {r['refleksi'] or '-'}")
                st.markdown(f"**Pelapor:** {r['pelapor'] or '-'} ({r['jawatan_pelapor'] or '-'})")
                st.markdown(f"**Penyemak:** {r['penyemak'] or '-'} ({r['jawatan_penyemak'] or '-'})")

            # Show images
            imgs = [p for p in [r["gambar_1_path"], r["gambar_2_path"]] if p and Path(p).exists()]
            if imgs:
                img_cols = st.columns(len(imgs))
                for i, p in enumerate(imgs):
                    with img_cols[i]:
                        st.image(p, use_container_width=True)

            # Actions
            ac1, ac2 = st.columns(2)
            with ac1:
                if r["pdf_path"] and Path(r["pdf_path"]).exists():
                    with open(r["pdf_path"], "rb") as f:
                        st.download_button(
                            "⬇ Muat Turun PDF",
                            f.read(),
                            file_name=f"LPR-{int(r['id']):06d}.pdf",
                            mime="application/pdf",
                            key=f"dl_{r['id']}",
                            use_container_width=True
                        )
            with ac2:
                if st.button("🗑 Padam Laporan", key=f"del_{r['id']}", use_container_width=True):
                    conn = get_conn()
                    conn.execute("DELETE FROM laporan WHERE id=?", (int(r["id"]),))
                    conn.execute("DELETE FROM kehadiran WHERE laporan_id=?", (int(r["id"]),))
                    conn.commit()
                    conn.close()
                    st.success("Laporan dipadam.")
                    st.rerun()


# =========================================================
# PAGE: KEHADIRAN STATS
# =========================================================
def page_kehadiran():
    st.markdown('<div class="section-title">STATISTIK KEHADIRAN</div>', unsafe_allow_html=True)

    reports = get_all_reports()
    kehadiran_df = get_kehadiran_log()

    if reports.empty:
        st.info("Tiada data kehadiran lagi. Sila hantar laporan dahulu.")
        return

    total_laporan = len(reports)
    total_hadir = reports["jumlah_hadir"].sum()
    total_murid = reports["jumlah_murid"].sum()
    pct = round(total_hadir / total_murid * 100) if total_murid else 0
    pasukan_aktif = reports["pasukan"].nunique()

    # Stat cards
    cs = st.columns(4)
    stats = [
        ("Jumlah Laporan", total_laporan),
        ("Pasukan Aktif", pasukan_aktif),
        ("Total Kehadiran", f"{int(total_hadir)} / {int(total_murid)}"),
        ("Peratus Kehadiran", f"{pct}%"),
    ]
    for col, (lbl, val) in zip(cs, stats):
        with col:
            st.markdown(
                f'<div class="stat-card"><div class="label">{lbl}</div><div class="val">{val}</div></div>',
                unsafe_allow_html=True
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # By pasukan
    st.markdown('<div class="sub-section-title">Kehadiran Mengikut Pasukan</div>', unsafe_allow_html=True)
    by_pasukan = reports.groupby("pasukan").agg(
        Perjumpaan=("id", "count"),
        Hadir=("jumlah_hadir", "sum"),
        Total=("jumlah_murid", "sum"),
    ).reset_index()
    by_pasukan["Peratus"] = (by_pasukan["Hadir"] / by_pasukan["Total"] * 100).round(1).fillna(0)
    by_pasukan = by_pasukan.rename(columns={"pasukan": "Pasukan"})

    st.dataframe(
        by_pasukan,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Peratus": st.column_config.ProgressColumn(
                "Peratus Kehadiran", format="%.1f%%", min_value=0, max_value=100
            ),
        }
    )

    # Bar chart
    st.bar_chart(by_pasukan.set_index("Pasukan")["Peratus"], height=240)

    # Per murid
    if not kehadiran_df.empty:
        st.markdown('<div class="sub-section-title">Kehadiran Per Murid</div>', unsafe_allow_html=True)
        per_murid = kehadiran_df.groupby(["nama_murid", "kelas", "pasukan"]).agg(
            Hadir=("status", lambda s: (s == "H").sum()),
            Total=("status", "count"),
        ).reset_index()
        per_murid["Peratus"] = (per_murid["Hadir"] / per_murid["Total"] * 100).round(1).fillna(0)
        per_murid = per_murid.rename(columns={"nama_murid": "Nama", "kelas": "Kelas", "pasukan": "Pasukan"})
        per_murid = per_murid.sort_values("Peratus", ascending=False)

        st.dataframe(
            per_murid,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Peratus": st.column_config.ProgressColumn(
                    "Peratus Kehadiran", format="%.1f%%", min_value=0, max_value=100
                ),
            }
        )

    # Export
    st.markdown("<br>", unsafe_allow_html=True)
    csv = reports.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Muat Turun Semua Laporan (CSV)", csv,
                       file_name="laporan-kokurikulum.csv", mime="text/csv")


# =========================================================
# PAGE: PENTADBIRAN
# =========================================================
def page_admin():
    # ===== Password gate =====
    if not st.session_state.get("admin_authenticated", False):
        st.markdown('<div class="section-title">🔒 PENTADBIRAN — LOG MASUK</div>', unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            st.markdown(
                '<div style="background:#fff;border:1px solid var(--line);border-radius:10px;'
                'padding:24px;margin-top:12px;box-shadow:0 2px 8px rgba(0,0,0,0.04)">',
                unsafe_allow_html=True
            )
            st.markdown(
                '<p style="color:var(--ink-soft);font-size:14px;margin-bottom:14px">'
                'Tab Pentadbiran dilindungi kata laluan. Sila masukkan kata laluan untuk mengakses tetapan '
                'sekolah, data komponen, pasukan, guru dan murid.</p>',
                unsafe_allow_html=True
            )

            with st.form("admin_login", clear_on_submit=False):
                pw = st.text_input("Kata Laluan", type="password",
                                   placeholder="Masukkan kata laluan pentadbir")
                submit = st.form_submit_button("Log Masuk", type="primary", use_container_width=True)

            if submit:
                if verify_admin_password(pw):
                    st.session_state.admin_authenticated = True
                    st.success("✅ Log masuk berjaya.")
                    st.rerun()
                else:
                    st.error("❌ Kata laluan salah.")

            st.markdown(
                '<p style="color:var(--ink-faint);font-size:12px;margin-top:14px;text-align:center">'
                'Kata laluan lalai: <code>admin123</code> — sila tukar selepas log masuk pertama.</p>',
                unsafe_allow_html=True
            )
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # ===== Authenticated — show admin panel =====
    head_col1, head_col2 = st.columns([5, 1])
    with head_col1:
        st.markdown('<div class="section-title">⚙ PENTADBIRAN</div>', unsafe_allow_html=True)
    with head_col2:
        if st.button("🚪 Log Keluar", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

    admin_tabs = st.tabs(["Tetapan", "Komponen", "Pasukan", "Guru", "Murid"])

    # --- Settings ---
    with admin_tabs[0]:
        st.markdown('<div class="sub-section-title">Tetapan Sekolah</div>', unsafe_allow_html=True)
        with st.form("settings_form"):
            sn = st.text_input("Nama Sekolah", value=get_setting("school_name"))
            at = st.text_input("Tajuk Aplikasi", value=get_setting("app_title"))
            lu = st.text_input("URL Logo Sekolah (pautan terus ke .png/.jpg)",
                              value=get_setting("school_logo_url"))
            if st.form_submit_button("Simpan Tetapan", type="primary"):
                set_setting("school_name", sn)
                set_setting("app_title", at)
                set_setting("school_logo_url", lu)
                st.success("Tetapan disimpan.")
                st.rerun()

        st.markdown("---")
        st.markdown('<div class="sub-section-title">🔑 Tukar Kata Laluan Pentadbir</div>',
                    unsafe_allow_html=True)
        with st.form("password_form", clear_on_submit=True):
            current_pw = st.text_input("Kata Laluan Semasa", type="password")
            new_pw = st.text_input("Kata Laluan Baharu", type="password")
            confirm_pw = st.text_input("Sahkan Kata Laluan Baharu", type="password")
            if st.form_submit_button("Tukar Kata Laluan", type="primary"):
                if not verify_admin_password(current_pw):
                    st.error("❌ Kata laluan semasa tidak betul.")
                elif len(new_pw) < 6:
                    st.error("❌ Kata laluan mesti sekurang-kurangnya 6 aksara.")
                elif new_pw != confirm_pw:
                    st.error("❌ Pengesahan kata laluan tidak sepadan.")
                else:
                    set_admin_password(new_pw)
                    st.success("✅ Kata laluan berjaya ditukar.")

    # --- Komponen ---
    with admin_tabs[1]:
        st.markdown('<div class="sub-section-title">Senarai Komponen</div>', unsafe_allow_html=True)
        conn = get_conn()
        df = pd.read_sql_query("SELECT id, nama FROM komponen ORDER BY nama", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.form("komp_form"):
            new_k = st.text_input("Komponen Baharu")
            if st.form_submit_button("Tambah", type="primary") and new_k:
                conn = get_conn()
                try:
                    conn.execute("INSERT INTO komponen (nama) VALUES (?)", (new_k,))
                    conn.commit()
                    st.success("Komponen ditambah.")
                except sqlite3.IntegrityError:
                    st.error("Komponen sudah wujud.")
                conn.close()
                st.rerun()

    # --- Pasukan ---
    with admin_tabs[2]:
        st.markdown('<div class="sub-section-title">Senarai Pasukan</div>', unsafe_allow_html=True)
        conn = get_conn()
        df = pd.read_sql_query("SELECT id, komponen, nama FROM pasukan ORDER BY komponen, nama", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.form("pasukan_form"):
            c = st.selectbox("Komponen", get_komponen())
            n = st.text_input("Nama Pasukan")
            if st.form_submit_button("Tambah", type="primary") and n:
                conn = get_conn()
                try:
                    conn.execute("INSERT INTO pasukan (komponen, nama) VALUES (?, ?)", (c, n))
                    conn.commit()
                    st.success("Pasukan ditambah.")
                except sqlite3.IntegrityError:
                    st.error("Pasukan sudah wujud.")
                conn.close()
                st.rerun()

    # --- Guru ---
    with admin_tabs[3]:
        st.markdown('<div class="sub-section-title">Senarai Guru Penasihat</div>', unsafe_allow_html=True)
        conn = get_conn()
        df = pd.read_sql_query("SELECT id, pasukan, nama FROM guru ORDER BY pasukan, nama", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.form("guru_form"):
            p = st.selectbox("Pasukan", get_pasukan())
            n = st.text_input("Nama Guru")
            if st.form_submit_button("Tambah", type="primary") and n:
                conn = get_conn()
                try:
                    conn.execute("INSERT INTO guru (pasukan, nama) VALUES (?, ?)", (p, n))
                    conn.commit()
                    st.success("Guru ditambah.")
                except sqlite3.IntegrityError:
                    st.error("Guru sudah wujud.")
                conn.close()
                st.rerun()

    # --- Murid ---
    with admin_tabs[4]:
        st.markdown('<div class="sub-section-title">Senarai Murid</div>', unsafe_allow_html=True)
        conn = get_conn()
        df = pd.read_sql_query("SELECT id, kelas, nama, pasukan FROM murid ORDER BY pasukan, kelas, nama", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("##### Tambah Murid")
        with st.form("murid_form"):
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                k = st.text_input("Kelas", placeholder="Contoh: 4 Bestari")
            with mc2:
                n = st.text_input("Nama Murid")
            with mc3:
                p = st.selectbox("Pasukan", get_pasukan())
            if st.form_submit_button("Tambah", type="primary") and k and n:
                conn = get_conn()
                conn.execute("INSERT INTO murid (kelas, nama, pasukan) VALUES (?, ?, ?)", (k, n, p))
                conn.commit()
                conn.close()
                st.success("Murid ditambah.")
                st.rerun()

        st.markdown("##### Import Pukal (CSV)")
        st.caption("Format CSV: kelas, nama, pasukan")
        up = st.file_uploader("Pilih fail CSV", type=["csv"])
        if up and st.button("Import", type="primary"):
            try:
                imp = pd.read_csv(up)
                required = {"kelas", "nama", "pasukan"}
                if not required.issubset(imp.columns.str.lower()):
                    st.error(f"CSV mesti ada lajur: {', '.join(required)}")
                else:
                    imp.columns = imp.columns.str.lower()
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.executemany("INSERT INTO murid (kelas, nama, pasukan) VALUES (?, ?, ?)",
                                    imp[["kelas", "nama", "pasukan"]].values.tolist())
                    conn.commit()
                    conn.close()
                    st.success(f"{len(imp)} murid diimport.")
                    st.rerun()
            except Exception as e:
                st.error(f"Ralat: {e}")


# =========================================================
# MAIN
# =========================================================
def main():
    st.set_page_config(
        page_title="E-Pelaporan Kokurikulum",
        page_icon="📋",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    init_db()
    apply_custom_css()
    init_session_state()

    # Header
    school_name = get_setting("school_name")
    app_title = get_setting("app_title")
    logo_url = get_setting("school_logo_url")

    st.markdown('<div class="app-header">', unsafe_allow_html=True)
    if logo_url:
        st.markdown(
            f'<img src="{logo_url}" style="width:88px;height:88px;object-fit:contain;margin:0 auto;display:block">',
            unsafe_allow_html=True
        )
    else:
        st.markdown('<div class="logo-fallback">SK</div>', unsafe_allow_html=True)
    st.markdown(f'<h1>{app_title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<h2>{school_name}</h2>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Tabs (lock icon on Pentadbiran when not authenticated)
    admin_label = "⚙ PENTADBIRAN" if st.session_state.get("admin_authenticated") else "🔒 PENTADBIRAN"
    tab_borang, tab_senarai, tab_kehadiran, tab_admin = st.tabs([
        "📝 BORANG", "📑 SENARAI", "📊 KEHADIRAN", admin_label
    ])

    with tab_borang:
        page_borang()
    with tab_senarai:
        page_senarai()
    with tab_kehadiran:
        page_kehadiran()
    with tab_admin:
        page_admin()


if __name__ == "__main__":
    main()
