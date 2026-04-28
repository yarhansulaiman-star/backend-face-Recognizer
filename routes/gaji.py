from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import date

from database import (
    koneksi, ambil_gaji, simpan_gaji,
    hitung_potongan_terlambat, ambil_riwayat_gaji,
    ambil_laporan, ambil_riwayat
)

gaji_bp = Blueprint("gaji", __name__)

NAMA_BULAN = ["","Januari","Februari","Maret","April","Mei","Juni",
              "Juli","Agustus","September","Oktober","November","Desember"]

NAMA_BULAN_SHORT = ["","Jan","Feb","Mar","Apr","Mei","Jun",
                    "Jul","Agu","Sep","Okt","Nov","Des"]

# =========================
# LAPORAN ABSEN
# =========================
@gaji_bp.route("/laporan", methods=["GET"])
@jwt_required()
def laporan():
    tanggal = request.args.get("tanggal") or str(date.today())
    data = ambil_laporan(tanggal)

    return jsonify({
        "sukses": True,
        "tanggal": tanggal,
        "total": len(data),
        "data": data
    })

# =========================
# RIWAYAT ABSEN USER
# =========================
@gaji_bp.route("/riwayat", methods=["GET"])
@jwt_required()
def riwayat():
    user_id = get_jwt_identity()

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT k.id, k.nama FROM karyawan k
            JOIN user u ON u.username = k.nama WHERE u.id = %s
        """, (user_id,))
        k = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not k:
        return jsonify({"sukses": False, "pesan": "Data karyawan tidak ditemukan"}), 404

    data = ambil_riwayat(k["id"])

    return jsonify({
        "sukses": True,
        "nama": k["nama"],
        "data": data
    })

# =========================
#  LIST KARYAWAN (HRD)
# =========================
@gaji_bp.route("/karyawan/list", methods=["GET"])
@jwt_required()
def list_karyawan():
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

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, nama, jabatan, departemen FROM karyawan ORDER BY nama ASC")
        data = cur.fetchall()
    finally:
        cur.close()
        db.close()

    return jsonify({
        "sukses": True,
        "data": data
    })

# =========================
#  CEK GAJI
# =========================
@gaji_bp.route("/gaji", methods=["GET"])
@jwt_required()
def gaji():
    user_id = get_jwt_identity()

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.role, k.id AS karyawan_id, k.nama, k.jabatan, k.departemen
            FROM user u LEFT JOIN karyawan k ON k.nama = u.username
            WHERE u.id = %s
        """, (user_id,))
        row = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not row:
        return jsonify({"sukses": False, "pesan": "User tidak ditemukan"}), 404

    bulan = request.args.get("bulan", date.today().month, type=int)
    tahun = request.args.get("tahun", date.today().year, type=int)

    # kalau HRD bisa pilih karyawan
    karyawan_id = request.args.get("karyawan_id", type=int) \
        if row["role"] in ("hrd", "admin") else row["karyawan_id"]

    if not karyawan_id:
        return jsonify({"sukses": False, "pesan": "Data karyawan tidak ditemukan"}), 404

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT nama, jabatan, departemen FROM karyawan WHERE id = %s", (karyawan_id,))
        k = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not k:
        return jsonify({"sukses": False, "pesan": "Karyawan tidak ditemukan"}), 404

    g = ambil_gaji(karyawan_id, bulan, tahun)
    if not g:
        return jsonify({"sukses": False, "pesan": "Data gaji belum diatur"}), 404

    _, potongan = hitung_potongan_terlambat(karyawan_id, bulan, tahun)

    total_tunjangan = (
        g["tunjangan_transport"] +
        g["tunjangan_makan"] +
        g["tunjangan_jabatan"]
    )

    total_penghasilan = g["gaji_pokok"] + total_tunjangan
    gaji_bersih = total_penghasilan - potongan

    return jsonify({
        "sukses": True,
        "data": {
            "nama": k["nama"],
            "jabatan": k["jabatan"],
            "periode": f"{NAMA_BULAN[bulan]} {tahun}",
            "gaji_pokok": g["gaji_pokok"],
            "tunjangan_transport": g["tunjangan_transport"],
            "tunjangan_makan": g["tunjangan_makan"],
            "tunjangan_jabatan": g["tunjangan_jabatan"],
            "total_penghasilan": total_penghasilan,
            "potongan": potongan,
            "gaji_bersih": gaji_bersih
        }
    })

# =========================
#  SET GAJI (HRD)
# =========================
@gaji_bp.route("/gaji/set", methods=["POST"])
@jwt_required()
def set_gaji():
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

    data = request.json

    ok, msg = simpan_gaji(
        karyawan_id=data.get("karyawan_id"),
        gaji_pokok=data.get("gaji_pokok", 0),
        tunjangan_transport=data.get("tunjangan_transport", 0),
        tunjangan_makan=data.get("tunjangan_makan", 0),
        tunjangan_jabatan=data.get("tunjangan_jabatan", 0),
        bulan=data.get("bulan"),
        tahun=data.get("tahun")
    )

    if not ok:
        return jsonify({"sukses": False, "pesan": msg}), 500

    return jsonify({"sukses": True, "pesan": "Data gaji berhasil disimpan"})

# =========================
#  RIWAYAT GAJI
# =========================
@gaji_bp.route("/gaji/riwayat", methods=["GET"])
@jwt_required()
def riwayat_gaji():
    user_id = get_jwt_identity()

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT k.id, k.nama FROM karyawan k
            JOIN user u ON u.username = k.nama WHERE u.id = %s
        """, (user_id,))
        k = cur.fetchone()
    finally:
        cur.close()
        db.close()

    if not k:
        return jsonify({"sukses": False, "pesan": "Karyawan tidak ditemukan"}), 404

    hasil = []
    for g in ambil_riwayat_gaji(k["id"]):
        _, potongan = hitung_potongan_terlambat(k["id"], g["bulan"], g["tahun"])

        total = (
            g["gaji_pokok"] +
            g["tunjangan_transport"] +
            g["tunjangan_makan"] +
            g["tunjangan_jabatan"]
        )

        hasil.append({
            "periode": f"{NAMA_BULAN_SHORT[g['bulan']]} {g['tahun']}",
            "gaji_pokok": g["gaji_pokok"],
            "potongan": potongan,
            "total_gaji": total - potongan
        })

    return jsonify({
        "sukses": True,
        "nama": k["nama"],
        "data": hasil
    })