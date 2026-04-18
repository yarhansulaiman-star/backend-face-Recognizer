from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token,
    verify_jwt_in_request, jwt_required, get_jwt_identity
)
from flask_cors import CORS
from datetime import timedelta

from face_recognizer import FaceRecognizer
from database import *
from config import SECRET_KEY

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)

jwt = JWTManager(app)
recog = FaceRecognizer()


# ===================== ERROR HANDLER JWT =====================
@jwt.invalid_token_loader
def invalid_token_callback(reason):
    return jsonify({"sukses": False, "pesan": f"Token tidak valid: {reason}"}), 401

@jwt.unauthorized_loader
def missing_token_callback(reason):
    return jsonify({"sukses": False, "pesan": f"Token tidak ditemukan: {reason}"}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    return jsonify({"sukses": False, "pesan": "Token kadaluarsa, silakan login ulang"}), 401

@app.errorhandler(422)
def handle_422(e):
    return jsonify({"sukses": False, "pesan": "Token JWT tidak valid atau tidak ada"}), 401


# ===================== LOGIN =====================
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"sukses": False, "pesan": "Username dan password wajib diisi"}), 400

    user = cek_login(username, password)

    if not user:
        return jsonify({"sukses": False, "pesan": "Username atau password salah"}), 401

    token = create_access_token(identity=str(user["id"]))

    return jsonify({
        "sukses":   True,
        "token":    token,
        "username": user["username"],
        "role":     user.get("role", "user")
    })


# ===================== REGISTER =====================
@app.route("/register/multi", methods=["POST"])
def register_multi():
    try:
        data = request.get_json(force=True)

        username   = data.get("username",   "").strip()
        password   = data.get("password",   "")
        email      = data.get("email",      "").strip()
        jabatan    = data.get("jabatan",    "").strip()
        departemen = data.get("departemen", "IT").strip()
        fotos      = data.get("fotos")

        if not username:
            return jsonify({"sukses": False, "pesan": "Username wajib diisi"}), 400
        if not password:
            return jsonify({"sukses": False, "pesan": "Password wajib diisi"}), 400
        if not email:
            return jsonify({"sukses": False, "pesan": "Email wajib diisi"}), 400
        if not jabatan:
            return jsonify({"sukses": False, "pesan": "Jabatan wajib diisi"}), 400
        if not fotos or not isinstance(fotos, list):
            return jsonify({"sukses": False, "pesan": "Foto tidak valid"}), 400
        if len(fotos) < 3:
            return jsonify({"sukses": False, "pesan": "Minimal 3 foto diperlukan"}), 400

        print(f"\n{'='*40}")
        print(f"REGISTER → USERNAME: {username}")
        print(f"EMAIL: {email} | JABATAN: {jabatan} | DEPT: {departemen}")
        print(f"JUMLAH FOTO: {len(fotos)}")

        # 1. Encode wajah dulu
        hasil = recog.daftar_wajah_multi(fotos, username)
        print(f"HASIL ENCODING: {hasil}")

        if not hasil["sukses"]:
            return jsonify(hasil), 400

        # 2. Simpan ke tabel karyawan
        ok, res = tambah_karyawan(username, email, jabatan, departemen)
        print(f"DEBUG tambah_karyawan → ok={ok}, res={res}")

        if not ok:
            recog.encodings.pop(username, None)
            recog.save()
            return jsonify({"sukses": False, "pesan": res}), 400

        # 3. Simpan ke tabel user
        ok_user, msg = tambah_user(username, password)
        print(f"DEBUG tambah_user → ok={ok_user}, msg={msg}")

        if not ok_user:
            hapus_karyawan(username)  # rollback karyawan
            recog.encodings.pop(username, None)
            recog.save()
            return jsonify({"sukses": False, "pesan": msg}), 400

        print(f"REGISTRASI BERHASIL → {username}")
        print(f"{'='*40}\n")

        return jsonify({
            "sukses":          True,
            "pesan":           "Registrasi berhasil",
            "jumlah_encoding": hasil["jumlah_encoding"]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"sukses": False, "pesan": str(e)}), 500


# ===================== ABSEN =====================
@app.route("/absen", methods=["POST"])
def absen():
    try:
        verify_jwt_in_request()
    except Exception as e:
        print(f"JWT ERROR: {e}")
        return jsonify({"sukses": False, "pesan": "Sesi tidak valid, silakan login ulang"}), 401

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"sukses": False, "pesan": "Body request tidak valid"}), 400

    if not data or "gambar" not in data or not data["gambar"]:
        return jsonify({"sukses": False, "pesan": "Gambar kosong"}), 400

    lat = data.get("latitude")
    lon = data.get("longitude")

    print(f"\n{'='*40}")
    print(f"ABSEN — PANJANG BASE64: {len(data['gambar'])}")
    print(f"LOKASI: {lat}, {lon}")

    hasil = recog.kenali_wajah(data["gambar"])
    print(f"HASIL FACE: {hasil}")

    if not hasil["sukses"]:
        return jsonify(hasil), 200

    db = koneksi()
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

    print(f"ABSEN BERHASIL → {hasil['nama']} | {tipe} | {status}")
    print(f"{'='*40}\n")

    return jsonify({
        "sukses":     True,
        "nama":       hasil["nama"],
        "jabatan":    k["jabatan"],
        "departemen": k["departemen"],
        "tipe":       tipe,
        "status":     status,
        "keyakinan":  hasil["keyakinan"],
        "alamat":     alamat or "",
        "pesan":      "Absen berhasil"
    })


# ===================== RIWAYAT =====================
@app.route("/riwayat", methods=["GET"])
@jwt_required()
def riwayat():
    user_id = get_jwt_identity()

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT k.id, k.nama
            FROM karyawan k
            JOIN user u ON u.username = k.nama
            WHERE u.id = %s
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
        "nama":   k["nama"],
        "data":   data
    })


# ===================== HEALTH CHECK =====================
@app.route("/health")
def health():
    return jsonify({
        "status":    "ok",
        "terdaftar": list(recog.encodings.keys())
    })


# ===================== HAPUS ENCODING =====================
@app.route("/hapus/<username>", methods=["DELETE"])
@jwt_required()
def hapus_encoding(username):
    if username not in recog.encodings:
        return jsonify({"sukses": False, "pesan": "Username tidak ditemukan"}), 404

    del recog.encodings[username]
    recog.save()

    return jsonify({"sukses": True, "pesan": f"Encoding {username} berhasil dihapus"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)