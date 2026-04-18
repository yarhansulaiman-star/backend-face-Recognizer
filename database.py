import mysql.connector
import hashlib
import requests
from config import DB_CONFIG
from datetime import date, datetime, time


def koneksi():
    return mysql.connector.connect(**DB_CONFIG)


def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()


# ===================== REVERSE GEOCODING =====================
def get_alamat(lat, lon):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1}
        headers = {"User-Agent": "absensi-karyawan-app/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        return data.get("display_name", f"{lat}, {lon}")
    except Exception as e:
        print(f"Gagal reverse geocoding: {e}")
        return f"{lat}, {lon}"


# ===================== USER =====================
def tambah_user(username, password):
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("SELECT id FROM user WHERE username=%s", (username,))
        if cur.fetchone():
            return False, "Username sudah ada"

        cur.execute(
            "INSERT INTO user(username, password, role, dibuat) VALUES(%s, %s, 'user', %s)",
            (username, hash_password(password), date.today())
        )
        db.commit()
        return True, "OK"
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        cur.close()
        db.close()


def cek_login(username, password):
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, username, role FROM user WHERE username=%s AND password=%s",
            (username, hash_password(password))
        )
        return cur.fetchone()
    finally:
        cur.close()
        db.close()


# ===================== KARYAWAN =====================
def tambah_karyawan(nama, email, jabatan, departemen):
    db = koneksi()
    cur = db.cursor()
    try:
        # Cek nama duplikat
        cur.execute("SELECT id FROM karyawan WHERE nama=%s", (nama,))
        if cur.fetchone():
            return False, "Nama sudah terdaftar, gunakan username lain"

        cur.execute(
            "INSERT INTO karyawan(nama, email, jabatan, departemen, tanggal_daftar) "
            "VALUES(%s, %s, %s, %s, %s)",
            (nama, email, jabatan, departemen, date.today())
        )
        db.commit()
        return True, cur.lastrowid
    except mysql.connector.IntegrityError as e:
        db.rollback()
        err = str(e)
        if "nama" in err:
            return False, "Nama sudah terdaftar, gunakan username lain"
        if "email" in err:
            return False, "Email sudah terdaftar"
        return False, err
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        cur.close()
        db.close()


def hapus_karyawan(nama):
    """Rollback: hapus karyawan kalau tambah_user gagal"""
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM karyawan WHERE nama=%s", (nama,))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"hapus_karyawan error: {e}")
    finally:
        cur.close()
        db.close()


# ===================== ABSEN =====================
def simpan_absen(karyawan_id, lat=None, lon=None):
    db = koneksi()
    cur = db.cursor()
    now = datetime.now()

    alamat = None
    if lat is not None and lon is not None:
        alamat = get_alamat(lat, lon)
        print(f"Alamat: {alamat}")

    try:
        cur.execute(
            "SELECT * FROM absensi WHERE karyawan_id=%s AND tanggal=%s",
            (karyawan_id, now.date())
        )
        ada = cur.fetchone()

        if ada:
            cur.execute("""
                UPDATE absensi
                SET jam_keluar=%s, latitude=%s, longitude=%s, alamat=%s
                WHERE karyawan_id=%s AND tanggal=%s
            """, (now.time(), lat, lon, alamat, karyawan_id, now.date()))
            tipe   = "keluar"
            status = "selesai"
        else:
            status = "tepat_waktu" if now.time() <= time(8, 0) else "terlambat"
            cur.execute("""
                INSERT INTO absensi(karyawan_id, tanggal, jam_masuk, status, latitude, longitude, alamat)
                VALUES(%s, %s, %s, %s, %s, %s, %s)
            """, (karyawan_id, now.date(), now.time(), status, lat, lon, alamat))
            tipe = "masuk"

        db.commit()
        return True, tipe, status, alamat

    except Exception as e:
        db.rollback()
        print(f"simpan_absen error: {e}")
        return False, "-", "-", None
    finally:
        cur.close()
        db.close()


# ===================== RIWAYAT =====================
def ambil_riwayat(karyawan_id):
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT tanggal, jam_masuk, jam_keluar, status, alamat
            FROM absensi
            WHERE karyawan_id = %s
            ORDER BY tanggal DESC
            LIMIT 30
        """, (karyawan_id,))
        rows = cur.fetchall()

        result = []
        for r in rows:
            result.append({
                "tanggal":    str(r["tanggal"]),
                "jam_masuk":  str(r["jam_masuk"])  if r["jam_masuk"]  else None,
                "jam_keluar": str(r["jam_keluar"]) if r["jam_keluar"] else None,
                "status":     r["status"],
                "alamat":     r["alamat"],
            })
        return result
    finally:
        cur.close()
        db.close()