from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from database import cek_login, tambah_karyawan, tambah_user, hapus_karyawan
from recognizer import recog
import time

auth_bp = Blueprint("auth", __name__)


# ===================== LOGIN =====================
@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(force=True)
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
        "role":     user.get("role", "user"),
        "user_id":  user["id"]
    })


# ===================== REGISTER =====================
@auth_bp.route("/register/multi", methods=["POST"])
def register_multi():
    try:
        data       = request.get_json(force=True)
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

        # ✅ Log ukuran tiap foto untuk memantau apakah sudah kecil
        for i, f in enumerate(fotos):
            print(f"  Foto {i+1}: {len(f)} chars (~{len(f) * 3 // 4 // 1024} KB)")

        start = time.time()
        hasil = recog.daftar_wajah_multi(fotos, username)
        print(f"Face encoding selesai dalam {time.time() - start:.2f} detik")

        print(f"HASIL ENCODING: {hasil}")
        if not hasil["sukses"]:
            return jsonify(hasil), 400

        ok, res = tambah_karyawan(username, email, jabatan, departemen)
        print(f"DEBUG tambah_karyawan → ok={ok}, res={res}")
        if not ok:
            recog.encodings.pop(username, None)
            recog.save()
            return jsonify({"sukses": False, "pesan": res}), 400

        ok_user, msg = tambah_user(username, password)
        print(f"DEBUG tambah_user → ok={ok_user}, msg={msg}")
        if not ok_user:
            hapus_karyawan(username)
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