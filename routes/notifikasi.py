from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from firebase_admin import messaging
from apscheduler.schedulers.background import BackgroundScheduler

from database import koneksi

notif_bp = Blueprint("notifikasi", __name__)


# ===================== FCM =====================
def kirim_notifikasi_fcm(fcm_token, title, body):
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=fcm_token,
        )
        response = messaging.send(message)
        print(f"✅ Notifikasi terkirim: {response}")
    except Exception as e:
        print(f"❌ Gagal kirim FCM: {e}")


@notif_bp.route("/simpan-fcm-token", methods=["POST"])
@jwt_required()
def simpan_fcm_token():
    user_id   = get_jwt_identity()
    fcm_token = request.json.get("fcm_token")

    db_conn = koneksi()
    cur     = db_conn.cursor()
    try:
        cur.execute("UPDATE user SET fcm_token = %s WHERE id = %s", (fcm_token, user_id))
        db_conn.commit()
    finally:
        cur.close()
        db_conn.close()

    return jsonify({"sukses": True})


# ===================== SCHEDULER =====================
def pengingat_absen_masuk():
    print("🔔 Cek pengingat absen masuk...")

    db_conn = koneksi()
    cur     = db_conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.fcm_token FROM user u
            WHERE u.fcm_token IS NOT NULL
            AND u.id NOT IN (
                SELECT u2.id FROM absensi a
                JOIN karyawan k ON k.id = a.karyawan_id
                JOIN user u2 ON u2.username = k.nama
                WHERE a.tanggal = CURDATE()
            )
        """)
        users = cur.fetchall()
    finally:
        cur.close()
        db_conn.close()

    for u in users:
        kirim_notifikasi_fcm(
            u["fcm_token"],
            "Pengingat Absen Masuk",
            "Jangan lupa absen masuk sekarang!"
        )

    print(f"✅ Pengingat masuk dikirim ke {len(users)} user")


def pengingat_absen_pulang():
    print("🔔 Cek pengingat absen pulang...")

    db_conn = koneksi()
    cur     = db_conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.fcm_token FROM user u
            WHERE u.fcm_token IS NOT NULL
            AND u.id IN (
                SELECT u2.id FROM absensi a
                JOIN karyawan k ON k.id = a.karyawan_id
                JOIN user u2 ON u2.username = k.nama
                WHERE a.tanggal = CURDATE()
                AND a.jam_keluar IS NULL
            )
        """)
        users = cur.fetchall()
    finally:
        cur.close()
        db_conn.close()

    for u in users:
        kirim_notifikasi_fcm(
            u["fcm_token"],
            "Pengingat Absen Pulang",
            "Jangan lupa absen pulang sekarang!"
        )

    print(f"✅ Pengingat pulang dikirim ke {len(users)} user")


# ===================== START SCHEDULER =====================
def start_scheduler():
    scheduler = BackgroundScheduler()

    scheduler.add_job(pengingat_absen_masuk,  "cron", hour=7,  minute=30)
    scheduler.add_job(pengingat_absen_pulang, "cron", hour=17, minute=0)

    scheduler.start()
    print("✅ Scheduler notifikasi aktif")