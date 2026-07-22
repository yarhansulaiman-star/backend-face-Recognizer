import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from firebase_admin import messaging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from database import koneksi

notif_bp = Blueprint("notifikasi", __name__)

# Ganti sesuai timezone kantor kamu
TIMEZONE = pytz.timezone("Asia/Jakarta")

# Setup logger khusus notifikasi, biar gampang dibedakan dari log lain
logger = logging.getLogger("notifikasi")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)


# ===================== FCM =====================
def kirim_notifikasi_fcm(fcm_token, title, body, data=None):
    """
    Kirim satu notifikasi FCM.
    Return True kalau sukses, False kalau gagal.
    Kalau token sudah tidak valid (unregistered), otomatis dibersihkan dari database.
    """
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=fcm_token,
        )
        response = messaging.send(message)
        logger.info(f"✅ Notifikasi terkirim: {response}")
        return True

    except messaging.UnregisteredError:
        # Token sudah tidak valid (app di-uninstall / token kadaluarsa)
        logger.warning(f"⚠️ Token tidak valid, membersihkan dari database: {fcm_token[:20]}...")
        _hapus_token_invalid(fcm_token)
        return False

    except Exception as e:
        logger.error(f"❌ Gagal kirim FCM: {e}")
        return False


def kirim_notifikasi_massal(users, title, body, data=None):
    """
    Kirim notifikasi ke banyak user sekaligus.
    users: list of dict, tiap dict minimal punya key 'fcm_token' dan 'id'.
    Return jumlah yang sukses terkirim.
    """
    sukses = 0
    for u in users:
        token = u.get("fcm_token")
        if not token:
            continue
        if kirim_notifikasi_fcm(token, title, body, data):
            sukses += 1
    return sukses


def _hapus_token_invalid(fcm_token):
    db_conn = koneksi()
    cur = db_conn.cursor()
    try:
        cur.execute("UPDATE user SET fcm_token = NULL WHERE fcm_token = %s", (fcm_token,))
        db_conn.commit()
    except Exception as e:
        logger.error(f"❌ Gagal membersihkan token invalid: {e}")
    finally:
        cur.close()
        db_conn.close()


@notif_bp.route("/simpan-fcm-token", methods=["POST"])
@jwt_required()
def simpan_fcm_token():
    user_id = get_jwt_identity()
    fcm_token = request.json.get("fcm_token")

    # Validasi: jangan simpan token kosong/None
    if not fcm_token or not isinstance(fcm_token, str) or fcm_token.strip() == "":
        return jsonify({"sukses": False, "pesan": "fcm_token tidak valid"}), 400

    db_conn = koneksi()
    cur = db_conn.cursor()
    try:
        cur.execute("UPDATE user SET fcm_token = %s WHERE id = %s", (fcm_token, user_id))
        db_conn.commit()
        logger.info(f"Token FCM disimpan untuk user_id={user_id}")
    except Exception as e:
        logger.error(f"❌ Gagal simpan fcm_token: {e}")
        return jsonify({"sukses": False, "pesan": "gagal menyimpan token"}), 500
    finally:
        cur.close()
        db_conn.close()

    return jsonify({"sukses": True})


# ===================== SCHEDULER =====================
def pengingat_absen_masuk():
    logger.info("🔔 Cek pengingat absen masuk...")

    db_conn = koneksi()
    cur = db_conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.id, u.fcm_token FROM user u
            WHERE u.fcm_token IS NOT NULL
            AND u.id NOT IN (
                SELECT u2.id FROM absensi a
                JOIN karyawan k ON k.id = a.karyawan_id
                JOIN user u2 ON u2.username = k.nama
                WHERE a.tanggal = CURDATE()
            )
        """)
        users = cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Gagal query pengingat masuk: {e}")
        return
    finally:
        cur.close()
        db_conn.close()

    terkirim = kirim_notifikasi_massal(
        users,
        "Pengingat Absen Masuk",
        "Jangan lupa absen masuk sekarang!",
        data={"tipe": "pengingat_masuk"},
    )

    logger.info(f"✅ Pengingat masuk dikirim ke {terkirim}/{len(users)} user")


def pengingat_absen_pulang():
    logger.info("🔔 Cek pengingat absen pulang...")

    db_conn = koneksi()
    cur = db_conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.id, u.fcm_token FROM user u
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
    except Exception as e:
        logger.error(f"❌ Gagal query pengingat pulang: {e}")
        return
    finally:
        cur.close()
        db_conn.close()

    terkirim = kirim_notifikasi_massal(
        users,
        "Pengingat Absen Pulang",
        "Jangan lupa absen pulang sekarang!",
        data={"tipe": "pengingat_pulang"},
    )

    logger.info(f"✅ Pengingat pulang dikirim ke {terkirim}/{len(users)} user")


# ===================== START SCHEDULER =====================
def start_scheduler():
    scheduler = BackgroundScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        pengingat_absen_masuk,
        CronTrigger(hour=7, minute=30, timezone=TIMEZONE),
        id="pengingat_masuk",
        replace_existing=True,
    )
    scheduler.add_job(
        pengingat_absen_pulang,
        CronTrigger(hour=17, minute=0, timezone=TIMEZONE),
        id="pengingat_pulang",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"✅ Scheduler notifikasi aktif (timezone: {TIMEZONE})")
    return scheduler


# ===================== TESTING MANUAL (khusus admin) =====================
def _pastikan_admin():
    """Helper: cek role user yang login. Sesuaikan dengan struktur JWT claims kamu."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    return claims.get("role") == "admin"


@notif_bp.route("/test-pengingat-masuk", methods=["GET"])
@jwt_required()
def test_pengingat_masuk():
    if not _pastikan_admin():
        return jsonify({"pesan": "Akses ditolak, khusus admin"}), 403
    pengingat_absen_masuk()
    return jsonify({"status": "Pengingat absen masuk dipanggil manual"})


@notif_bp.route("/test-pengingat-pulang", methods=["GET"])
@jwt_required()
def test_pengingat_pulang():
    if not _pastikan_admin():
        return jsonify({"pesan": "Akses ditolak, khusus admin"}), 403
    pengingat_absen_pulang()
    return jsonify({"status": "Pengingat absen pulang dipanggil manual"})


@notif_bp.route("/test-pengingat-semua", methods=["GET"])
@jwt_required()
def test_pengingat_semua():
    if not _pastikan_admin():
        return jsonify({"pesan": "Akses ditolak, khusus admin"}), 403
    pengingat_absen_masuk()
    pengingat_absen_pulang()
    return jsonify({"status": "Kedua pengingat (masuk & pulang) dipanggil manual"})