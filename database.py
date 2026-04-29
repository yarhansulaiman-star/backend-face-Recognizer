import mysql.connector
import hashlib
import requests
from config import DB_CONFIG
from datetime import date, datetime, time
import pytz

# Timezone WIB
WIB = pytz.timezone("Asia/Jakarta")

def koneksi():
    return mysql.connector.connect(**DB_CONFIG)

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def now_wib():
    """Waktu sekarang dalam WIB."""
    return datetime.now(WIB)


# ================= REVERSE GEOCODING =================
def get_alamat(lat, lon):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1}
        headers = {"User-Agent": "absensi-karyawan-app/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        return data.get("display_name", f"{lat}, {lon}")
    except Exception as e:
        print(f"⚠️ Gagal reverse geocoding: {e}")
        return f"{lat}, {lon}"


# ================= USER =================
def tambah_user(username, password):
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("SELECT id FROM user WHERE username=%s", (username,))
        if cur.fetchone():
            return False, "Username sudah ada"
        cur.execute(
            "INSERT INTO user(username, password, role, dibuat) VALUES(%s, %s, 'user', %s)",
            (username, hash_password(password), now_wib().date())
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
    cur.execute("""
        SELECT id, username, role 
        FROM user 
        WHERE username=%s AND password=%s
    """, (username, hash_password(password)))
    data = cur.fetchone()
    cur.close()
    db.close()
    return data


# ================= KARYAWAN =================
def tambah_karyawan(nama, email, jabatan, departemen):
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("SELECT id FROM karyawan WHERE nama=%s", (nama,))
        if cur.fetchone():
            return False, "Nama sudah terdaftar, gunakan username lain"
        cur.execute(
            "INSERT INTO karyawan(nama, email, jabatan, departemen, tanggal_daftar) VALUES(%s, %s, %s, %s, %s)",
            (nama, email, jabatan, departemen, now_wib().date())
        )
        db.commit()
        return True, cur.lastrowid
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        cur.close()
        db.close()


def hapus_karyawan(nama):
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("DELETE FROM karyawan WHERE nama=%s", (nama,))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        cur.close()
        db.close()


# ================= ABSEN =================
def simpan_absen(karyawan_id, lat=None, lon=None):
    db = koneksi()
    cur = db.cursor()
    now = now_wib()

    alamat = None
    if lat is not None and lon is not None:
        alamat = get_alamat(lat, lon)
        print(f"📍 Alamat: {alamat}")

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
        batas = now.replace(hour=8, minute=0, second=0, microsecond=0)
        status = "tepat_waktu" if now <= batas else "terlambat"
        cur.execute("""
            INSERT INTO absensi(karyawan_id, tanggal, jam_masuk, status, latitude, longitude, alamat)
            VALUES(%s, %s, %s, %s, %s, %s, %s)
        """, (karyawan_id, now.date(), now.time().replace(tzinfo=None), status, lat, lon, alamat))
        tipe = "masuk"

    db.commit()
    cur.close()
    db.close()
    return True, tipe, status, alamat


# ================= LAPORAN =================
def ambil_laporan(tanggal):
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT 
                k.nama,
                k.jabatan,
                k.departemen,
                TIME_FORMAT(a.jam_masuk,  '%H:%i') AS jam_masuk,
                TIME_FORMAT(a.jam_keluar, '%H:%i') AS jam_keluar,
                a.status,
                a.alamat
            FROM absensi a
            JOIN karyawan k ON k.id = a.karyawan_id
            WHERE a.tanggal = %s
            ORDER BY a.jam_masuk ASC
        """, (tanggal,))
        return cur.fetchall()
    except Exception as e:
        print(f"❌ ambil_laporan error: {e}")
        return []
    finally:
        cur.close()
        db.close()


# ================= GAJI =================

def ambil_gaji(karyawan_id, bulan=None, tahun=None):
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        if bulan and tahun:
            cur.execute("""
                SELECT gaji_pokok, tunjangan_transport, tunjangan_makan,
                       tunjangan_jabatan, bulan, tahun
                FROM gaji
                WHERE karyawan_id = %s AND bulan = %s AND tahun = %s
            """, (karyawan_id, bulan, tahun))
        else:
            cur.execute("""
                SELECT gaji_pokok, tunjangan_transport, tunjangan_makan,
                       tunjangan_jabatan, bulan, tahun
                FROM gaji
                WHERE karyawan_id = %s
                ORDER BY tahun DESC, bulan DESC
                LIMIT 1
            """, (karyawan_id,))
        return cur.fetchone()
    except Exception as e:
        print(f"ambil_gaji error: {e}")
        return None
    finally:
        try:
            cur.fetchall()   # kosongkan sisa result
        except Exception:
            pass
        cur.close()
        db.close()


def simpan_gaji(karyawan_id, gaji_pokok, tunjangan_transport,
                tunjangan_makan, tunjangan_jabatan, bulan, tahun):
    """
    Insert atau update data gaji karyawan (upsert).
    Dipanggil oleh admin untuk mengatur komponen gaji.
    """
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO gaji
                (karyawan_id, gaji_pokok, tunjangan_transport,
                 tunjangan_makan, tunjangan_jabatan, bulan, tahun)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                gaji_pokok           = VALUES(gaji_pokok),
                tunjangan_transport  = VALUES(tunjangan_transport),
                tunjangan_makan      = VALUES(tunjangan_makan),
                tunjangan_jabatan    = VALUES(tunjangan_jabatan),
                diperbarui           = CURRENT_TIMESTAMP
        """, (karyawan_id, gaji_pokok, tunjangan_transport,
              tunjangan_makan, tunjangan_jabatan, bulan, tahun))
        db.commit()
        return True, "OK"
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        cur.close()
        db.close()


def hitung_potongan_terlambat(karyawan_id, bulan, tahun):
    """
    Hitung potongan keterlambatan dengan detail per hari.
    Tarif: Rp 1.000 per menit terlambat dari jam 08:00.
    Return: (list_detail, total_potongan)
    """
    POTONGAN_PER_MENIT = 1000

    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                DATE_FORMAT(tanggal, '%d %b %Y') AS tanggal,
                TIME_FORMAT(jam_masuk, '%H:%i')  AS jam_masuk,
                GREATEST(0, TIMESTAMPDIFF(MINUTE, '08:00:00', jam_masuk)) AS menit_terlambat
            FROM absensi
            WHERE karyawan_id = %s
              AND status = 'terlambat'
              AND MONTH(tanggal) = %s
              AND YEAR(tanggal)  = %s
            ORDER BY tanggal ASC
        """, (karyawan_id, bulan, tahun))
        rows = cur.fetchall()
        total_potongan = 0
        for row in rows:
            menit = int(row["menit_terlambat"] or 0)
            row["menit_terlambat"] = menit
            row["potongan"] = menit * POTONGAN_PER_MENIT
            total_potongan += row["potongan"]
        return rows, total_potongan   # (list detail, total rupiah)
    except Exception as e:
        print(f"hitung_potongan_terlambat error: {e}")
        return [], 0
    finally:
        cur.close()
        db.close()


def hitung_alpha(karyawan_id, bulan, tahun):
    """
    Hitung jumlah hari tidak hadir tanpa keterangan (alpha).
    Return: int jumlah hari alpha
    """
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT COUNT(*) AS jumlah
            FROM absensi
            WHERE karyawan_id = %s
              AND status = 'alpha'
              AND MONTH(tanggal) = %s
              AND YEAR(tanggal)  = %s
        """, (karyawan_id, bulan, tahun))
        row = cur.fetchone()
        return int(row["jumlah"]) if row else 0
    except Exception as e:
        print(f"hitung_alpha error: {e}")
        return 0
    finally:
        cur.close()
        db.close()


def ambil_riwayat_gaji(karyawan_id, limit=6):
    """
    Ambil ringkasan gaji beberapa bulan terakhir untuk riwayat.
    """
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT gaji_pokok, tunjangan_transport, tunjangan_makan,
                   tunjangan_jabatan, bulan, tahun
            FROM gaji
            WHERE karyawan_id = %s
            ORDER BY tahun DESC, bulan DESC
            LIMIT %s
        """, (karyawan_id, limit))
        return cur.fetchall()
    except Exception as e:
        print(f"ambil_riwayat_gaji error: {e}")
        return []
    finally:
        cur.close()
        db.close()


# ================= RIWAYAT =================
def ambil_riwayat(karyawan_id):
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT 
                DATE_FORMAT(tanggal, '%a, %d %b %Y') AS tanggal,
                TIME_FORMAT(jam_masuk,  '%H:%i') AS jam_masuk,
                TIME_FORMAT(jam_keluar, '%H:%i') AS jam_keluar,
                status,
                alamat
            FROM absensi
            WHERE karyawan_id = %s
            ORDER BY tanggal DESC
            LIMIT 30
        """, (karyawan_id,))
        return cur.fetchall()
    except Exception as e:
        print(f"❌ ambil_riwayat error: {e}")
        return []
    finally:
        cur.close()
        db.close()


# ================= SURAT IZIN =================
def ajukan_izin(user_id, jenis_izin, tanggal_mulai, tanggal_selesai, keterangan, foto_bukti=None):
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO surat_izin
                (user_id, jenis_izin, tanggal_mulai, tanggal_selesai,
                 keterangan, foto_bukti, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'menunggu', %s)
        """, (user_id, jenis_izin, tanggal_mulai, tanggal_selesai,
              keterangan, foto_bukti, now_wib()))
        db.commit()
        return True, cur.lastrowid
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        cur.close()
        db.close()


def ambil_izin_karyawan(user_id):
    """Ambil surat izin milik karyawan sendiri."""
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                si.id, si.user_id,
                k.nama AS nama_karyawan,
                si.jenis_izin, si.tanggal_mulai, si.tanggal_selesai,
                si.keterangan, si.foto_bukti, si.status,
                si.catatan_hrd, si.created_at
            FROM surat_izin si
            JOIN user u ON u.id = si.user_id
            JOIN karyawan k ON k.nama = u.username
            WHERE si.user_id = %s
            ORDER BY si.created_at DESC
        """, (user_id,))
        return cur.fetchall()
    except Exception as e:
        print(f"ambil_izin_karyawan error: {e}")
        return []
    finally:
        cur.close()
        db.close()


def ambil_semua_izin():
    """Ambil semua surat izin — untuk HRD/admin."""
    db = koneksi()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                si.id, si.user_id,
                k.nama AS nama_karyawan,
                si.jenis_izin, si.tanggal_mulai, si.tanggal_selesai,
                si.keterangan, si.foto_bukti, si.status,
                si.catatan_hrd, si.created_at
            FROM surat_izin si
            JOIN user u ON u.id = si.user_id
            JOIN karyawan k ON k.nama = u.username
            ORDER BY si.created_at DESC
        """)
        return cur.fetchall()
    except Exception as e:
        print(f"ambil_semua_izin error: {e}")
        return []
    finally:
        cur.close()
        db.close()


def update_status_izin(izin_id, status, catatan_hrd=None):
    """Update status izin — dipanggil HRD untuk setujui/tolak."""
    db = koneksi()
    cur = db.cursor()
    try:
        cur.execute("""
            UPDATE surat_izin
            SET status = %s, catatan_hrd = %s
            WHERE id = %s
        """, (status, catatan_hrd, izin_id))
        db.commit()
        return True, "OK"
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        cur.close()
        db.close()