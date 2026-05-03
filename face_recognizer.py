import numpy as np
import cv2
import base64
import os
import pickle
from deepface import DeepFace


class FaceRecognizer:
    def __init__(self):
        self.file        = "encodings.pkl"
        self.encodings   = {}
        self.model_name  = "ArcFace"

        self.THRESHOLD       = 0.50   # jarak maksimum untuk diterima
        self.MARGIN_MIN      = 0.05   # selisih minimum antar kandidat
        self.MIN_MATCH_RATIO = 0.25   # minimal 25% encoding harus cocok

        # ✅ Keyakinan minimum yang diterima server: 50%
        # Score 0.50 → confidence = (1 - 0.50) * 100 = 50%
        self.MIN_CONFIDENCE  = 50.0

        if os.path.exists(self.file):
            with open(self.file, "rb") as f:
                self.encodings = pickle.load(f)
            print(f"✅ Encodings dimuat: {len(self.encodings)} user → {list(self.encodings.keys())}")
        else:
            print("⚠️  encodings.pkl belum ada, mulai dari kosong")

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
        h, w     = img.shape[:2]
        target_w = 640
        scale    = target_w / w
        new_h    = int(h * scale)
        img      = cv2.resize(img, (target_w, new_h), interpolation=cv2.INTER_LINEAR)
        lab      = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b  = cv2.split(lab)
        clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l        = clahe.apply(l)
        lab      = cv2.merge((l, a, b))
        img      = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return img

    def encode(self, img):
        if img is None:
            return None
        try:
            img    = self.preprocess(img)
            rgb    = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            result = DeepFace.represent(
                img_path          = rgb,
                model_name        = self.model_name,
                enforce_detection = False,
                detector_backend  = "opencv"
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
                    print(f"  ❌ Foto {idx + 1} [{label}] gagal encode")

        print(f"TOTAL ENCODING untuk [{nama}]: {len(hasil)}")

        if len(hasil) < 3:
            return {"sukses": False, "pesan": "Wajah kurang jelas / tidak konsisten, ulangi foto"}

        self.encodings[nama] = hasil
        self.save()
        print(f"✅ Encoding disimpan. Semua user: {list(self.encodings.keys())}")
        return {"sukses": True, "jumlah_encoding": len(hasil)}

    def kenali_wajah(self, b64):
        print(f"\n🔍 kenali_wajah() — encodings tersedia: {list(self.encodings.keys())}")

        img = self.base64_to_img(b64)
        if img is None:
            return {"sukses": False, "pesan": "Gambar tidak valid"}

        enc = self.encode(img)
        if enc is None:
            return {"sukses": False, "pesan": "Wajah tidak terdeteksi"}

        if not self.encodings:
            return {"sukses": False, "pesan": "Belum ada data wajah terdaftar"}

        scores = {}

        for n, encs in self.encodings.items():
            distances   = [self._cosine_distance(enc, e) for e in encs]
            cocok       = [d for d in distances if d < self.THRESHOLD]
            ratio_cocok = len(cocok) / len(distances)

            avg     = np.mean(distances)
            median  = np.median(distances)
            minimum = np.min(distances)

            score = (minimum * 0.5) + (avg * 0.3) + (median * 0.2)

            print(
                f"  [{n}] avg={avg:.4f} median={median:.4f} "
                f"min={minimum:.4f} score={score:.4f} "
                f"cocok={len(cocok)}/{len(distances)} ({ratio_cocok:.0%})"
            )

            if ratio_cocok < self.MIN_MATCH_RATIO:
                print(f"  [{n}] ❌ Ditolak — ratio cocok rendah ({ratio_cocok:.0%})")
                scores[n] = 999
                continue

            scores[n] = score

        if not scores:
            return {"sukses": False, "pesan": "Tidak dikenali"}

        sorted_candidates = sorted(scores.items(), key=lambda x: x[1])
        best_nama, best_score = sorted_candidates[0]

        print(f"  BEST: {best_nama} score={best_score:.4f}")

        if best_score > self.THRESHOLD:
            return {"sukses": False, "pesan": "Wajah tidak dikenali"}

        if len(sorted_candidates) > 1:
            second_nama, second_score = sorted_candidates[1]
            margin = second_score - best_score
            print(f"  MARGIN: {margin:.4f} (second={second_nama} {second_score:.4f})")
            if second_score != 999 and margin < self.MARGIN_MIN:
                print(f"  ❌ Ditolak — margin terlalu kecil ({margin:.4f})")
                return {"sukses": False, "pesan": "Wajah tidak dapat dikenali dengan pasti"}

        # ✅ FIX: konversi ke float Python biasa (bukan np.float64)
        # np.float64 bisa menyebabkan masalah serialisasi JSON di beberapa versi
        confidence = round(float((1 - best_score) * 100), 2)

        # ✅ Cek keyakinan minimum 50%
        if confidence < self.MIN_CONFIDENCE:
            print(f"  ❌ Ditolak — keyakinan {confidence}% < minimum {self.MIN_CONFIDENCE}%")
            return {"sukses": False, "pesan": f"Keyakinan terlalu rendah ({confidence}%)"}

        print(f"  ✅ Dikenali: {best_nama} ({confidence}%)")
        return {
            "sukses"    : True,
            "nama"      : best_nama,
            "keyakinan" : confidence   # ← float biasa, bukan np.float64
        }

    def debug_raw_score(self, b64):
        img = self.base64_to_img(b64)
        if img is None:
            return {"error": "Gambar tidak valid"}
        enc = self.encode(img)
        if enc is None:
            return {"error": "Wajah tidak terdeteksi"}

        result = {}
        for n, encs in self.encodings.items():
            distances = [self._cosine_distance(enc, e) for e in encs]
            result[n] = {
                "min"   : round(float(np.min(distances)),    4),
                "avg"   : round(float(np.mean(distances)),   4),
                "median": round(float(np.median(distances)), 4),
                "score" : round(
                    float(np.min(distances))    * 0.5 +
                    float(np.mean(distances))   * 0.3 +
                    float(np.median(distances)) * 0.2,
                    4
                ),
            }
        return result

    def hapus_wajah(self, nama):
        if nama not in self.encodings:
            return {"sukses": False, "pesan": f"{nama} tidak ditemukan"}
        del self.encodings[nama]
        self.save()
        return {"sukses": True, "pesan": f"{nama} berhasil dihapus"}

    def _cosine_distance(self, a, b):
        a  = np.array(a)
        b  = np.array(b)
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 1.0
        return 1 - np.dot(a, b) / (na * nb)


recog = FaceRecognizer()