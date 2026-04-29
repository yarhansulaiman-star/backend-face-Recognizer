from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from database import koneksi, simpan_absen, ambil_riwayat
from face_recognizer import recog

absen_bp = Blueprint("absen", __name__)


# ===================== ABSEN =====================
@absen_bp.route("/absen", methods=["POST"])
def absen():
    try:
        verify_jwt_in_request()
    except Exception:
        return jsonify({"sukses": False, "pesan": "Sesi tidak valid, silakan login ulang"}), 401

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"sukses": False, "pesan": "Body request tidak valid"}), 400

    if not data or "gambar" not in data or not data["gambar"]:
        return jsonify({"sukses": False, "pesan": "Gambar kosong"}), 400

    lat = data.get("latitude")
    lon = data.get("longitude")

    hasil = recog.kenali_wajah(data["gambar"])
    if not hasil["sukses"]:
        return jsonify(hasil), 200

    db  = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM karyawan WHERE nama = %s", (hasil["nama"],))
        k = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not k:
        return jsonify({"sukses": False, "pesan": "Karyawan tidak ditemukan di database"}), 404

    ok, tipe, status, alamat = simpan_absen(k["id"], lat, lon)
    if not ok:
        return jsonify({"sukses": False, "pesan": "Gagal menyimpan absen"}), 500

    return jsonify({
        "sukses"    : True,
        "nama"      : hasil["nama"],
        "jabatan"   : k["jabatan"],
        "departemen": k["departemen"],
        "tipe"      : tipe,
        "status"    : status,
        "keyakinan" : hasil["keyakinan"],
        "alamat"    : alamat or "",
        "pesan"     : "Absen berhasil"
    })


# ===================== KENALI =====================
@absen_bp.route("/kenali", methods=["POST"])
def kenali():
    data   = request.json
    gambar = data.get("gambar")
    hasil  = recog.kenali_wajah(gambar)
    return jsonify(hasil)


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

    return jsonify({
        "sukses": True,
        "data"  : data
    })