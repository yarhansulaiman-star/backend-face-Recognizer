from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

from database import koneksi, ambil_laporan

laporan_bp = Blueprint("laporan", __name__)


# ===================== LIST KARYAWAN =====================
@laporan_bp.route("/karyawan/list", methods=["GET"])
def list_karyawan():
    try:
        verify_jwt_in_request()
    except Exception:
        return jsonify({"sukses": False, "pesan": "Sesi tidak valid, silakan login ulang"}), 401

    db  = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT k.id, k.nama, k.email, k.jabatan, k.departemen,
                   k.tanggal_daftar, u.role
            FROM karyawan k
            JOIN user u ON u.username = k.nama
            ORDER BY k.nama ASC
        """)
        data = cur.fetchall()
    except Exception as e:
        return jsonify({"sukses": False, "pesan": str(e)}), 500
    finally:
        cur.close()
        db.close()

    return jsonify({
        "sukses": True,
        "data"  : data
    })


# ===================== LAPORAN ABSEN =====================
@laporan_bp.route("/laporan", methods=["GET"])
def laporan():
    try:
        verify_jwt_in_request()
    except Exception:
        return jsonify({"sukses": False, "pesan": "Sesi tidak valid, silakan login ulang"}), 401

    tanggal = request.args.get("tanggal")
    if not tanggal:
        from database import now_wib
        tanggal = now_wib().date().isoformat()

    data = ambil_laporan(tanggal)

    return jsonify({
        "sukses"  : True,
        "tanggal" : tanggal,
        "data"    : data
    })