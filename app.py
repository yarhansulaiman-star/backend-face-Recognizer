import firebase_admin
from firebase_admin import credentials
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from datetime import timedelta

from config import SECRET_KEY

from auth import auth_bp
from routes.absen import absen_bp
from routes.gaji import gaji_bp
from routes.izin import izin_bp
from routes.notifikasi import notif_bp, start_scheduler
from routes.laporan import laporan_bp


# ===================== INIT APP =====================
app = Flask(__name__)
CORS(app)


# ===================== FIREBASE =====================
cred = credentials.Certificate("absenkantor-83eaa-58039e8f1892.json")
firebase_admin.initialize_app(cred)


# ===================== JWT =====================
app.config["JWT_SECRET_KEY"]           = SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)

jwt = JWTManager(app)


# ===================== JWT ERROR HANDLERS =====================
@jwt.invalid_token_loader
def invalid_token_callback(reason):
    return jsonify({"sukses": False, "pesan": f"Token tidak valid: {reason}"}), 401

@jwt.unauthorized_loader
def missing_token_callback(reason):
    return jsonify({"sukses": False, "pesan": f"Token tidak ditemukan: {reason}"}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_data):
    return jsonify({"sukses": False, "pesan": "Token kadaluarsa"}), 401

@app.errorhandler(422)
def handle_422(e):
    return jsonify({"sukses": False, "pesan": "JWT tidak valid"}), 401


# ===================== HEALTH CHECK =====================
@app.route("/health")
def health():
    # ✅ Import dari face_recognizer
    from face_recognizer import recog
    return jsonify({
        "status"    : "ok",
        "total_user": len(recog.encodings),
        "users"     : list(recog.encodings.keys())
    })


# ===================== HAPUS ENCODING =====================
@app.route("/hapus/<username>", methods=["DELETE"])
def hapus_encoding(username):
    from face_recognizer import recog
    hasil = recog.hapus_wajah(username)
    if not hasil["sukses"]:
        return jsonify(hasil), 404
    return jsonify(hasil)


# ===================== REGISTER ROUTES =====================
app.register_blueprint(auth_bp)
app.register_blueprint(absen_bp)
app.register_blueprint(gaji_bp)
app.register_blueprint(izin_bp)
app.register_blueprint(notif_bp)
app.register_blueprint(laporan_bp)


# ===================== START SCHEDULER =====================
start_scheduler()


# ===================== RUN =====================
if __name__ == "__main__":
    # debug=False — mencegah Flask restart 2x (double import = 2 instance recog)
    app.run(debug=False, host="0.0.0.0", port=5000)