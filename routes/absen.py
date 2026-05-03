"""
routes/absen.py
===============
Import recog dari face_recognizer — instance yang SAMA dengan auth.py
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from database import koneksi, simpan_absen, ambil_riwayat

# ✅ Sama dengan auth.py — satu instance, satu encodings.pkl
from face_recognizer import recog

absen_bp = Blueprint("absen", __name__)


# ===================== ABSEN =====================
@absen_bp.route("/absen", methods=["POST"])
def absen():
    # ── Auth ──────────────────────────────────────────────────────────────
    try:
        verify_jwt_in_request()
    except Exception:
        return jsonify({"sukses": False, "pesan": "Sesi tidak valid, silakan login ulang"}), 401

    # ── Parse body ────────────────────────────────────────────────────────
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"sukses": False, "pesan": "Body request tidak valid"}), 400

    if not data or "gambar" not in data or not data["gambar"]:
        return jsonify({"sukses": False, "pesan": "Gambar kosong"}), 400

    lat = data.get("latitude")
    lon = data.get("longitude")

    # ── Kenali wajah ──────────────────────────────────────────────────────
    hasil = recog.kenali_wajah(data["gambar"])
    print(f"[ABSEN] kenali_wajah → {hasil}")

    if not hasil["sukses"]:
        return jsonify(hasil), 200

    # ── Cari karyawan di DB ───────────────────────────────────────────────
    # hasil["nama"] = username yang disimpan saat register
    # karyawan.nama = username yang disimpan oleh tambah_karyawan
    # Keduanya harus sama persis
    db  = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM karyawan WHERE nama = %s", (hasil["nama"],))
        k = cur.fetchone()
        print(f"[ABSEN] query karyawan '{hasil['nama']}' → {k}")
    finally:
        cur.close()
        db.close()

    if not k:
        return jsonify({
            "sukses": False,
            "pesan" : f"Karyawan '{hasil['nama']}' tidak ditemukan di database"
        }), 404

    # ── Simpan absen ──────────────────────────────────────────────────────
    ok, tipe, status, alamat = simpan_absen(k["id"], lat, lon)
    if not ok:
        return jsonify({"sukses": False, "pesan": "Gagal menyimpan absen"}), 500

    return jsonify({
        "sukses"     : True,
        "nama"       : hasil["nama"],
        "jabatan"    : k["jabatan"],
        "departemen" : k["departemen"],
        "tipe"       : tipe,
        "status"     : status,
        "keyakinan"  : hasil["keyakinan"],
        "alamat"     : alamat or "",
        "pesan"      : "Absen berhasil"
    })


# ===================== KENALI (preview tanpa simpan) =====================
@absen_bp.route("/kenali", methods=["POST"])
def kenali():
    try:
        data   = request.get_json(force=True)
        gambar = data.get("gambar")
    except Exception:
        return jsonify({"sukses": False, "pesan": "Body request tidak valid"}), 400

    if not gambar:
        return jsonify({"sukses": False, "pesan": "Gambar kosong"}), 400

    hasil = recog.kenali_wajah(gambar)
    return jsonify(hasil)


# ===================== DEBUG SCORE =====================
@absen_bp.route("/debug_score", methods=["POST"])
def debug_score():
    """
    Tampilkan raw distance semua user tanpa penolakan.
    Gunakan untuk kalibrasi threshold.
    """
    try:
        data   = request.get_json(force=True)
        gambar = data.get("gambar")
    except Exception:
        return jsonify({"error": "Body request tidak valid"}), 400

    if not gambar:
        return jsonify({"error": "Gambar kosong"}), 400

    result = recog.debug_raw_score(gambar)
    return jsonify(result)


# ===================== RIWAYAT =====================
@absen_bp.route("/riwayat", methods=["GET"])
def riwayat():
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
    except Exception:
        return jsonify({"sukses": False, "pesan": "Sesi tidak valid, silakan login ulang"}), 401

    db  = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT k.id FROM karyawan k
            JOIN user u ON u.username = k.nama
            WHERE u.id = %s
        """, (user_id,))
        karyawan = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not karyawan:
        return jsonify({"sukses": False, "pesan": "Karyawan tidak ditemukan"}), 404

    data = ambil_riwayat(karyawan["id"])
    return jsonify({"sukses": True, "data": data})