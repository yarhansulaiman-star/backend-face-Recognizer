import numpy as np
import cv2
import base64
import os
import pickle
from deepface import DeepFace


class FaceRecognizer:
    def __init__(self):
        self.file       = "encodings.pkl"
        self.encodings  = {}
        self.model_name = "ArcFace"

        # ✅ FIX: Threshold lebih ketat — ArcFace cosine distance
        # < 0.30  → sangat yakin (sama orang)
        # 0.30–0.40 → cukup yakin
        # > 0.40  → tolak (beda orang)
        self.THRESHOLD          = 0.35   # threshold utama
        self.MARGIN_MIN         = 0.08   # selisih minimum antar kandidat terbaik
        self.MIN_MATCH_RATIO    = 0.40   # minimal 40% encoding harus cocok

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
            nparr     = np.frombuffer(img_bytes, np.uint8)
            img       = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                print("  ❌ cv2.imdecode gagal")
            return img
        except Exception as e:
            print(f"  ❌ base64_to_img error: {e}")
            return None

    def preprocess(self, img):
        h, w       = img.shape[:2]
        target_w   = 640
        scale      = target_w / w
        new_h      = int(h * scale)
        img        = cv2.resize(img, (target_w, new_h), interpolation=cv2.INTER_LINEAR)

        lab        = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b    = cv2.split(lab)
        clahe      = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l          = clahe.apply(l)
        lab        = cv2.merge((l, a, b))
        img        = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return img

    def encode(self, img):
        if img is None:
            return None
        try:
            img    = self.preprocess(img)
            rgb    = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            result = DeepFace.represent(
                img_path         = rgb,
                model_name       = self.model_name,
                enforce_detection= False,
                detector_backend = "opencv"
            )
            return np.array(result[0]["embedding"])
        except Exception as e:
            print(f"  ❌ encode error: {e}")
            return None

    def daftar_wajah_multi(self, fotos, nama):
        hasil = []
        for idx, f in enumerate(fotos):
            img = self.base64_to_img(f)
            if img is None:
                print(f"  ❌ Foto {idx + 1}: gagal decode base64")
                continue

            variasi = [
                ("asli",        img),
                ("mirror",      cv2.flip(img, 1)),
                ("cerah",       cv2.convertScaleAbs(img, alpha=1.2, beta=10)),
                ("gelap",       cv2.convertScaleAbs(img, alpha=0.8, beta=-10)),
                ("blur_ringan", cv2.GaussianBlur(img, (3, 3), 0)),
            ]
            for label, im in variasi:
                enc = self.encode(im)
                if enc is not None:
                    hasil.append(enc)
                    print(f"  ✅ Foto {idx + 1} [{label}] berhasil di-encode")
                else:
                    print(f"  ❌ Foto {idx + 1} [{label}] gagal")

        print(f"TOTAL ENCODING BERHASIL: {len(hasil)}")
        if len(hasil) < 3:
            return {"sukses": False, "pesan": "Wajah kurang jelas / tidak konsisten"}

        self.encodings[nama] = hasil
        self.save()
        return {"sukses": True, "jumlah_encoding": len(hasil)}

    def kenali_wajah(self, b64):
        img = self.base64_to_img(b64)
        if img is None:
            return {"sukses": False, "pesan": "Gambar tidak valid"}

        enc = self.encode(img)
        if enc is None:
            return {"sukses": False, "pesan": "Wajah tidak terdeteksi"}

        if not self.encodings:
            return {"sukses": False, "pesan": "Belum ada data wajah terdaftar"}

        scores = {}  # nama → score akhir

        for n, encs in self.encodings.items():
            distances = [self._cosine_distance(enc, e) for e in encs]

            # ✅ FIX: Hitung berapa encoding yang benar-benar cocok (di bawah threshold)
            cocok = [d for d in distances if d < self.THRESHOLD]
            ratio_cocok = len(cocok) / len(distances)

            avg     = np.mean(distances)
            minimum = np.min(distances)

            # ✅ FIX: Score baru — lebih ketat, tidak mudah tertipu 1 foto mirip
            # Gunakan median + mean agar tidak mudah dipengaruhi outlier
            median  = np.median(distances)
            score   = (avg * 0.4) + (median * 0.4) + (minimum * 0.2)

            print(f"  [{n}] avg={avg:.4f}, median={median:.4f}, "
                  f"min={minimum:.4f}, score={score:.4f}, "
                  f"cocok={len(cocok)}/{len(distances)} ({ratio_cocok:.0%})")

            # ✅ FIX: Tolak langsung jika ratio encoding yang cocok terlalu sedikit
            if ratio_cocok < self.MIN_MATCH_RATIO:
                print(f"  [{n}] ❌ Ditolak — ratio cocok terlalu rendah ({ratio_cocok:.0%})")
                scores[n] = 999  # nilai buruk
                continue

            scores[n] = score

        if not scores:
            return {"sukses": False, "pesan": "Tidak dikenali"}

        # Urutkan kandidat dari score terbaik
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1])
        best_nama, best_score = sorted_candidates[0]

        print(f"DEBUG BEST: {best_nama} score={best_score:.4f}")

        # ✅ FIX: Threshold lebih ketat
        if best_score > self.THRESHOLD:
            return {"sukses": False, "pesan": "Tidak dikenali"}

        # ✅ FIX: Cek margin — jika kandidat ke-2 terlalu dekat, tolak (tidak yakin)
        if len(sorted_candidates) > 1:
            second_nama, second_score = sorted_candidates[1]
            margin = second_score - best_score
            print(f"DEBUG MARGIN: {margin:.4f} "
                  f"(best={best_nama} {best_score:.4f}, "
                  f"second={second_nama} {second_score:.4f})")

            if margin < self.MARGIN_MIN:
                print(f"  ❌ Ditolak — margin terlalu kecil ({margin:.4f}), tidak yakin")
                return {"sukses": False, "pesan": "Wajah tidak dapat dikenali dengan pasti"}

        confidence = round((1 - best_score) * 100, 2)
        # ✅ FIX: Confidence minimum 70% agar tidak asal cocok
        if confidence < 70.0:
            return {"sukses": False, "pesan": "Tidak dikenali"}

        return {"sukses": True, "nama": best_nama, "keyakinan": confidence}

    def _cosine_distance(self, a, b):
        a = np.array(a)
        b = np.array(b)
        return 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# Instance global — diimport oleh routes/absen.py
recog = FaceRecognizer()