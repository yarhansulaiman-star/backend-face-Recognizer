import face_recognition
import numpy as np
import cv2
import base64
import os
import pickle


class FaceRecognizer:
    def __init__(self):
        self.file = "encodings.pkl"
        self.encodings = {}

        if os.path.exists(self.file):
            with open(self.file, "rb") as f:
                self.encodings = pickle.load(f)

    def save(self):
        with open(self.file, "wb") as f:
            pickle.dump(self.encodings, f)

    def base64_to_img(self, b64):
        try:
            if "," in b64:
                b64 = b64.split(",")[1]

            img_bytes = base64.b64decode(b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                print("  ❌ cv2.imdecode gagal")
            return img
        except Exception as e:
            print(f"  ❌ base64_to_img error: {e}")
            return None

    def preprocess(self, img):
        h, w = img.shape[:2]

        # Resize proporsional ke lebar 640
        target_w = 640
        scale = target_w / w
        new_h = int(h * scale)
        img = cv2.resize(img, (target_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Normalisasi pencahayaan CLAHE
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return img

    def detect_face_locations(self, rgb):
        """
        Deteksi lokasi wajah bertahap.
        Jika semua gagal, gunakan seluruh gambar sebagai area wajah (fallback emulator).
        """
        # HOG upsample=1
        loc = face_recognition.face_locations(
            rgb, model="hog", number_of_times_to_upsample=1
        )
        if loc:
            print("  ✔ Deteksi: HOG upsample=1")
            return loc, False

        # HOG upsample=2
        print("  ⚠️ HOG upsample=1 gagal, coba upsample=2...")
        loc = face_recognition.face_locations(
            rgb, model="hog", number_of_times_to_upsample=2
        )
        if loc:
            print("  ✔ Deteksi: HOG upsample=2")
            return loc, False

        # HOG upsample=3
        print("  ⚠️ HOG upsample=2 gagal, coba upsample=3...")
        loc = face_recognition.face_locations(
            rgb, model="hog", number_of_times_to_upsample=3
        )
        if loc:
            print("  ✔ Deteksi: HOG upsample=3")
            return loc, False

        # CNN normal
        print("  ⚠️ HOG gagal semua, mencoba CNN...")
        loc = face_recognition.face_locations(rgb, model="cnn")
        if loc:
            print("  ✔ Deteksi: CNN")
            return loc, False

        # Fallback: gunakan seluruh gambar sebagai area wajah
        h, w = rgb.shape[:2]
        print("  ⚠️ Semua model gagal, pakai full-frame fallback...")
        loc = [(0, w, h, 0)]  # (top, right, bottom, left)
        return loc, True  # True = fallback mode

    def encode(self, img):
        if img is None:
            return None

        img = self.preprocess(img)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        loc, is_fallback = self.detect_face_locations(rgb)

        if not loc:
            return None

        if is_fallback:
            # Fallback: crop tengah gambar sebagai area wajah
            h, w = rgb.shape[:2]
            margin_h = int(h * 0.1)
            margin_w = int(w * 0.1)
            loc = [(margin_h, w - margin_w, h - margin_h, margin_w)]
            print("  ✔ Encode: full-frame fallback (crop tengah)")

        enc = face_recognition.face_encodings(rgb, loc, num_jitters=1)
        return enc[0] if enc else None

    # ===================== REGISTER =====================
    def daftar_wajah_multi(self, fotos, nama):
        hasil = []

        for idx, f in enumerate(fotos):
            img = self.base64_to_img(f)

            if img is None:
                print(f"  ❌ Foto {idx + 1}: gagal decode base64")
                continue

            variasi = [
                ("asli",   img),
                ("mirror", cv2.flip(img, 1)),
                ("cerah",  cv2.convertScaleAbs(img, alpha=1.2, beta=10)),
            ]

            for label, im in variasi:
                enc = self.encode(im)
                if enc is not None:
                    hasil.append(enc)
                    print(f"  ✅ Foto {idx + 1} [{label}] berhasil di-encode")
                else:
                    print(f"  ❌ Foto {idx + 1} [{label}] gagal — wajah tidak terdeteksi")

        print(f"TOTAL ENCODING BERHASIL: {len(hasil)}")

        if len(hasil) < 3:
            return {
                "sukses": False,
                "pesan": "Wajah kurang jelas / tidak konsisten"
            }

        self.encodings[nama] = hasil
        self.save()

        return {
            "sukses": True,
            "jumlah_encoding": len(hasil)
        }

    # ===================== ABSEN =====================
    def kenali_wajah(self, b64):
        img = self.base64_to_img(b64)

        if img is None:
            return {"sukses": False, "pesan": "Gambar tidak valid"}

        enc = self.encode(img)

        if enc is None:
            return {"sukses": False, "pesan": "Wajah tidak terdeteksi"}

        if not self.encodings:
            return {"sukses": False, "pesan": "Belum ada data wajah terdaftar"}

        best_score = 999
        nama = None

        for n, encs in self.encodings.items():
            distances = face_recognition.face_distance(encs, enc)

            avg = np.mean(distances)
            minimum = np.min(distances)

            score = (avg * 0.6) + (minimum * 0.4)

            print(f"  [{n}] avg={avg:.4f}, min={minimum:.4f}, score={score:.4f}")

            if score < best_score:
                best_score = score
                nama = n

        print(f"DEBUG BEST SCORE: {best_score:.4f} → {nama}")

        if best_score > 0.65:
            return {"sukses": False, "pesan": "Tidak dikenali"}

        confidence = round((1 - best_score) * 100, 2)

        return {
            "sukses": True,
            "nama": nama,
            "keyakinan": confidence
        }