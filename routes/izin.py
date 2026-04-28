from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity


from database import (
    koneksi, ajukan_izin, ambil_izin_karyawan,
    ambil_semua_izin, update_status_izin
)

izin_bp = Blueprint("izin", __name__)


# =========================
#  KIRIM SURAT IZIN
# =========================
@izin_bp.route("/surat-izin", methods=["POST"])
@jwt_required()
def kirim_surat_izin():
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True)

    jenis_izin      = data.get("jenis_izin", "").strip()
    tanggal_mulai   = data.get("tanggal_mulai", "").strip()
    tanggal_selesai = data.get("tanggal_selesai", "").strip()
    keterangan      = data.get("keterangan", "").strip()
    foto_bukti      = data.get("foto_bukti")

    if not jenis_izin or not tanggal_mulai or not tanggal_selesai or not keterangan:
        return jsonify({"sukses": False, "pesan": "Semua field wajib diisi"}), 400

    ok, result = ajukan_izin(
        user_id, jenis_izin, tanggal_mulai,
        tanggal_selesai, keterangan, foto_bukti
    )

    if not ok:
        return jsonify({"sukses": False, "pesan": result}), 500

    return jsonify({
        "sukses": True,
        "pesan": "Surat izin berhasil dikirim",
        "id": result
    })


# =========================
#  IZIN SAYA
# =========================
@izin_bp.route("/surat-izin", methods=["GET"])
@jwt_required()
def get_surat_izin_saya():
    user_id = int(get_jwt_identity())

    return jsonify({
        "sukses": True,
        "data": ambil_izin_karyawan(user_id)
    })


# =========================
#  SEMUA IZIN (HRD)
# =========================
@izin_bp.route("/surat-izin/semua", methods=["GET"])
@jwt_required()
def get_semua_surat_izin():
    user_id = get_jwt_identity()

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT role FROM user WHERE id = %s", (user_id,))
        u = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not u or u["role"] not in ("hrd", "admin"):
        return jsonify({"sukses": False, "pesan": "Akses ditolak"}), 403

    return jsonify({
        "sukses": True,
        "data": ambil_semua_izin()
    })


# =========================
#  UPDATE STATUS IZIN
# =========================
@izin_bp.route("/surat-izin/update-status", methods=["POST"])
@jwt_required()
def update_izin():
    user_id = get_jwt_identity()

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT role FROM user WHERE id = %s", (user_id,))
        u = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not u or u["role"] not in ("hrd", "admin"):
        return jsonify({"sukses": False, "pesan": "Akses ditolak"}), 403

    data        = request.get_json(force=True)
    izin_id     = data.get("izin_id")
    status      = data.get("status")
    catatan_hrd = data.get("catatan_hrd", "")

    if not izin_id or status not in ("disetujui", "ditolak"):
        return jsonify({"sukses": False, "pesan": "Data tidak valid"}), 400

    ok, msg = update_status_izin(izin_id, status, catatan_hrd)

    if not ok:
        return jsonify({"sukses": False, "pesan": msg}), 500

    return jsonify({
        "sukses": True,
        "pesan": f"Izin berhasil {status}"
    })