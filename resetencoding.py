"""
reset_encoding.py
─────────────────
Script utilitas untuk mengelola file encodings.pkl tanpa perlu
menjalankan server Flask.

Cara pakai:
  python reset_encoding.py              → tampilkan info semua encoding
  python reset_encoding.py --list       → sama seperti di atas
  python reset_encoding.py --reset admin    → hapus encoding 'admin'
  python reset_encoding.py --reset-all      → hapus SEMUA encoding
  python reset_encoding.py --backup         → backup encodings.pkl
  python reset_encoding.py --restore         → restore dari backup
"""

import pickle
import os
import sys
import shutil
from datetime import datetime

ENCODING_FILE = "encodings.pkl"
BACKUP_FILE   = f"encodings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"


def load():
    if not os.path.exists(ENCODING_FILE):
        print(f"[!] File '{ENCODING_FILE}' tidak ditemukan.")
        return {}
    with open(ENCODING_FILE, "rb") as f:
        data = pickle.load(f)
    # Normalisasi: pastikan semua value berupa list
    return {k: (v if isinstance(v, list) else [v]) for k, v in data.items()}


def save(data):
    with open(ENCODING_FILE, "wb") as f:
        pickle.dump(data, f)
    print(f"[✓] Encoding disimpan ke '{ENCODING_FILE}'")


def tampilkan_info(data):
    if not data:
        print("[ ] Tidak ada encoding terdaftar.")
        return
    print(f"\n{'─'*45}")
    print(f"  {'NAMA':<25} {'ENCODING':>10}")
    print(f"{'─'*45}")
    total = 0
    for nama, enc_list in sorted(data.items()):
        print(f"  {nama:<25} {len(enc_list):>10}")
        total += len(enc_list)
    print(f"{'─'*45}")
    print(f"  {'TOTAL USER':<25} {len(data):>10}")
    print(f"  {'TOTAL ENCODING':<25} {total:>10}")
    print(f"{'─'*45}\n")


def reset_satu(nama):
    data = load()
    if nama not in data:
        print(f"[!] '{nama}' tidak ditemukan. User terdaftar: {list(data.keys())}")
        return
    del data[nama]
    save(data)
    print(f"[✓] Encoding '{nama}' berhasil dihapus.")
    print(f"[i] Silakan register ulang '{nama}' melalui endpoint /register/multi")


def reset_semua():
    konfirmasi = input("⚠️  Hapus SEMUA encoding? Ketik 'ya' untuk konfirmasi: ").strip()
    if konfirmasi.lower() != "ya":
        print("[i] Dibatalkan.")
        return
    save({})
    print("[✓] Semua encoding dihapus.")


def backup():
    if not os.path.exists(ENCODING_FILE):
        print(f"[!] '{ENCODING_FILE}' tidak ditemukan.")
        return
    shutil.copy(ENCODING_FILE, BACKUP_FILE)
    print(f"[✓] Backup disimpan ke '{BACKUP_FILE}'")


def restore():
    backups = sorted(
        [f for f in os.listdir(".") if f.startswith("encodings_backup_")],
        reverse=True
    )
    if not backups:
        print("[!] Tidak ada file backup ditemukan.")
        return
    latest = backups[0]
    print(f"[i] File backup terbaru: {latest}")
    konfirmasi = input("Restore dari file ini? Ketik 'ya': ").strip()
    if konfirmasi.lower() != "ya":
        print("[i] Dibatalkan.")
        return
    shutil.copy(latest, ENCODING_FILE)
    print(f"[✓] Encoding berhasil direstore dari '{latest}'")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("--list", "-l"):
        data = load()
        tampilkan_info(data)

    elif args[0] == "--reset" and len(args) >= 2:
        reset_satu(args[1])

    elif args[0] == "--reset-all":
        reset_semua()

    elif args[0] == "--backup":
        backup()

    elif args[0] == "--restore":
        restore()

    else:
        print(__doc__)