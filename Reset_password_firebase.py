import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, render_template_string

import mysql.connector
from config import DB_CONFIG, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, APP_BASE_URL
from database import hash_password  # ✅ pakai fungsi hash yang SAMA dengan cek_login()

reset_bp = Blueprint("reset_bp", __name__)

TOKEN_EXPIRED_MENIT = 30  # link reset berlaku 30 menit


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def kirim_email(ke_email: str, subjek: str, isi_html: str):
    """Kirim email lewat SMTP (misal Gmail App Password)."""
    pesan = MIMEText(isi_html, "html")
    pesan["Subject"] = subjek
    pesan["From"] = SMTP_USER
    pesan["To"] = ke_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [ke_email], pesan.as_string())


# ===================== 1. REQUEST RESET (generate token sendiri + kirim email sendiri) =====================
@reset_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"sukses": False, "pesan": "Email wajib diisi"}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # ✅ email ada di tabel karyawan, dan karyawan.nama = user.username
    cursor.execute("""
        SELECT k.id AS karyawan_id, k.email, u.username
        FROM karyawan k
        JOIN user u ON u.username = k.nama
        WHERE k.email = %s
    """, (email,))
    user = cursor.fetchone()

    # ✅ Selalu balas sukses meski email tidak ditemukan (best practice keamanan,
    # supaya orang tidak bisa "menebak" email mana yang terdaftar)
    if not user:
        cursor.close()
        conn.close()
        return jsonify({"sukses": True, "pesan": "Kalau email terdaftar, link reset sudah dikirim."})

    # Buat token acak yang aman, simpan ke DB dengan waktu kedaluwarsa
    token = secrets.token_urlsafe(32)
    sekarang = datetime.now()
    kadaluarsa = sekarang + timedelta(minutes=TOKEN_EXPIRED_MENIT)

    cursor2 = conn.cursor()
    cursor2.execute("""
        INSERT INTO password_reset_token (email, token, dibuat, kadaluarsa, sudah_dipakai)
        VALUES (%s, %s, %s, %s, 0)
    """, (email, token, sekarang, kadaluarsa))
    conn.commit()
    cursor2.close()
    cursor.close()
    conn.close()

    link_reset = f"{APP_BASE_URL}/reset-password?token={token}"

    isi_email = f"""
    <p>Halo,</p>
    <p>Kami menerima permintaan reset password untuk akun Absensi Karyawan kamu.</p>
    <p><a href="{link_reset}">Klik di sini untuk membuat password baru</a></p>
    <p>Link ini berlaku selama {TOKEN_EXPIRED_MENIT} menit. Kalau kamu tidak meminta reset password, abaikan email ini.</p>
    <p>Terima kasih,<br>Tim Absensi Karyawan</p>
    """

    try:
        kirim_email(email, "Reset Password - Absensi Karyawan", isi_email)
    except Exception as e:
        print(f"⚠️ Gagal kirim email reset password: {e}")
        return jsonify({"sukses": False, "pesan": "Gagal mengirim email. Coba lagi nanti."}), 500

    return jsonify({"sukses": True, "pesan": "Kalau email terdaftar, link reset sudah dikirim."})


# ===================== 2. HALAMAN FORM RESET (dibuka dari link email) =====================
FORM_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Password</title>
    <style>
        body { font-family: Arial, sans-serif; background:#f5f5f5; display:flex;
               justify-content:center; align-items:center; height:100vh; margin:0; }
        .card { background:#fff; padding:32px; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,.1);
                width:100%; max-width:360px; }
        h2 { color:#2196F3; margin-top:0; }
        input { width:100%; padding:10px; margin:8px 0; border:1px solid #ccc; border-radius:6px;
                box-sizing:border-box; }
        button { width:100%; padding:12px; background:#2196F3; color:#fff; border:none;
                 border-radius:6px; font-weight:bold; cursor:pointer; margin-top:8px; }
        .pesan { margin-top:12px; font-size:14px; }
        .error { color:#D32F2F; }
        .sukses { color:#2E7D32; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Buat Password Baru</h2>
        <form id="formReset">
            <input type="password" id="passwordBaru" placeholder="Password baru" required minlength="6">
            <input type="password" id="konfirmasi" placeholder="Konfirmasi password baru" required minlength="6">
            <button type="submit">Simpan Password</button>
        </form>
        <div id="pesan" class="pesan"></div>
    </div>

    <script>
        const token = "{{ token }}";
        const form = document.getElementById("formReset");
        const pesanEl = document.getElementById("pesan");

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const passwordBaru = document.getElementById("passwordBaru").value;
            const konfirmasi = document.getElementById("konfirmasi").value;

            if (passwordBaru !== konfirmasi) {
                pesanEl.innerHTML = '<span class="error">Password tidak cocok</span>';
                return;
            }

            const res = await fetch("/reset-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: token, password_baru: passwordBaru })
            });
            const data = await res.json();

            if (data.sukses) {
                pesanEl.innerHTML = '<span class="sukses">' + data.pesan + '</span>';
                form.style.display = "none";
            } else {
                pesanEl.innerHTML = '<span class="error">' + data.pesan + '</span>';
            }
        });
    </script>
</body>
</html>
"""


@reset_bp.route("/reset-password", methods=["GET"])
def halaman_reset_password():
    token = request.args.get("token", "")
    if not token:
        return "<h3>Link tidak valid.</h3>", 400
    return render_template_string(FORM_HTML, token=token)


# ===================== 3. SUBMIT PASSWORD BARU (verifikasi token + update MySQL) =====================
@reset_bp.route("/reset-password", methods=["POST"])
def submit_reset_password():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    password_baru = data.get("password_baru", "")

    if not token or not password_baru:
        return jsonify({"sukses": False, "pesan": "Data tidak lengkap"}), 400
    if len(password_baru) < 6:
        return jsonify({"sukses": False, "pesan": "Password minimal 6 karakter"}), 400

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM password_reset_token
        WHERE token = %s
    """, (token,))
    baris_token = cursor.fetchone()

    if not baris_token:
        cursor.close()
        conn.close()
        return jsonify({"sukses": False, "pesan": "Link tidak valid"}), 400

    if baris_token["sudah_dipakai"]:
        cursor.close()
        conn.close()
        return jsonify({"sukses": False, "pesan": "Link ini sudah pernah dipakai"}), 400

    if datetime.now() > baris_token["kadaluarsa"]:
        cursor.close()
        conn.close()
        return jsonify({"sukses": False, "pesan": "Link sudah kedaluwarsa, silakan minta link baru"}), 400

    email = baris_token["email"]

    # Cari username lewat email di tabel karyawan, lalu update password di tabel user
    cursor.execute("SELECT nama FROM karyawan WHERE email = %s", (email,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return jsonify({"sukses": False, "pesan": "Email tidak terdaftar di sistem"}), 404

    username = row["nama"]

    # ✅ pakai hash_password() yang sama persis dengan yang dipakai cek_login()
    password_hash = hash_password(password_baru)

    cursor2 = conn.cursor()
    cursor2.execute("UPDATE user SET password = %s WHERE username = %s", (password_hash, username))
    cursor2.execute("UPDATE password_reset_token SET sudah_dipakai = 1 WHERE token = %s", (token,))
    conn.commit()
    cursor2.close()
    cursor.close()
    conn.close()

    return jsonify({"sukses": True, "pesan": "Password berhasil diubah, silakan login dengan password baru."})