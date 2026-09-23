# 🎭 Backend Face Recognizer

REST API untuk sistem **absensi karyawan berbasis pengenalan wajah**. Dibangun dengan **Flask**, terintegrasi dengan **Firebase** (autentikasi & notifikasi), **MySQL** sebagai database, dan **DeepFace / OpenCV** untuk pengenalan wajah.

> Merupakan bagian backend dari ekosistem aplikasi Android [**absensi_kantor**](https://github.com/yarhansulaiman-star/absensi_kantor).

---

## ✨ Fitur

- 🔐 Autentikasi JWT — login, register, dan reset password (via Firebase)
- 👁️ Pengenalan wajah untuk absen masuk & pulang
- 🕒 Pencatatan absensi dan riwayat kehadiran
- 📄 Pengajuan serta persetujuan surat izin
- 💰 Manajemen dan perhitungan gaji karyawan
- 📊 Laporan kehadiran
- 🔔 Notifikasi push (Firebase Cloud Messaging) + scheduler pengingat absen otomatis

---

## 🛠️ Tech Stack

| Bagian | Teknologi |
|---|---|
| Framework | Flask |
| Autentikasi | Flask-JWT-Extended, Firebase Admin |
| Database | MySQL |
| Face Recognition | DeepFace, OpenCV |
| Notifikasi | Firebase Cloud Messaging |
| Scheduler | APScheduler |

---

## 📂 Struktur Proyek

```
backend-face-Recognizer/
├── app.py                    # Entry point aplikasi Flask
├── auth.py                   # Endpoint autentikasi
├── database.py               # Koneksi & query MySQL
├── face_recognizer.py        # Logika pengenalan wajah (DeepFace)
├── recognizer.py
├── resetencoding.py
├── Reset_password_firebase.py
├── routes/
│   ├── absen.py              # Endpoint absensi
│   ├── gaji.py               # Endpoint gaji
│   ├── izin.py               # Endpoint surat izin
│   ├── laporan.py            # Endpoint laporan
│   └── notifikasi.py         # Notifikasi & scheduler
└── .env.example
```

---

## 🚀 Cara Menjalankan

```bash
# 1. Clone repository
git clone https://github.com/yarhansulaiman-star/backend-face-Recognizer.git
cd backend-face-Recognizer

# 2. Buat & aktifkan virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# 3. Install dependency
pip install -r requirements.txt

# 4. Salin konfigurasi environment
copy .env.example .env         # Windows
# cp .env.example .env         # Linux / macOS

# 5. Jalankan server
python app.py
```

---

## ⚙️ Environment Variables

| Variabel | Keterangan |
|---|---|
| `SECRET_KEY` | Secret key untuk JWT |
| `DB_HOST` | Host database MySQL |
| `DB_USER` | Username database |
| `DB_PASS` | Password database |
| `DB_NAME` | Nama database |
| `DB_CHARSET` | Charset koneksi database |

---

## 🔒 Catatan Keamanan

File berikut **tidak boleh** ikut ter-commit (sudah masuk `.gitignore`):

- `.env` dan `config.py`
- Service account Firebase (`absenkantor-*.json`)
- `encodings.pkl` (data biometrik wajah)
- Foto absensi karyawan (`foto_absen/`)

---

## 👤 Author

**Ahmed Yarhan Sulaiman** · [@yarhansulaiman-star](https://github.com/yarhansulaiman-star)
