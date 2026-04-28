from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request

from database import koneksi, simpan_absen
from face_recognizer import recog

absen_bp = Blueprint("absen", __name__)

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
        "sukses": True,
        "nama": hasil["nama"],
        "jabatan": k["jabatan"],
        "departemen": k["departemen"],
        "tipe": tipe,
        "status": status,
        "keyakinan": hasil["keyakinan"],
        "alamat": alamat or "",
        "pesan": "Absen berhasil"
    })


@absen_bp.route("/kenali", methods=["POST"])
def kenali():
    data = request.json
    gambar = data.get("gambar")
    hasil = recog.kenali_wajah(gambar)
    return jsonify(hasil)