# 🗳️ Panduan Backup & Restore Data SIAPA

Berikut adalah perintah-perintah resmi untuk melakukan backup (dump) dan mengembalikan (load) data di Django.

---

## 💾 1. Cara Backup (Data Dump)

Gunakan perintah ini untuk menyimpan data dari database ke file JSON.

### A. Backup Seluruh Database (Paling Komplit)
```powershell
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission --indent 4 > backup_full.json
```
*Catatan: `-e` digunakan untuk mengecualikan data sistem yang sering bikin error saat restore.*

### B. Backup Per Aplikasi (Misal: Hanya App Core)
```powershell
python manage.py dumpdata core --indent 4 > backup_core.json
```

---

## 📥 2. Cara Restore (Load Data)

Gunakan perintah ini untuk memasukkan kembali data dari file JSON ke database baru.

### Langkah-langkah:
1. Pastikan database dalam keadaan kosong (sudah di-`migrate`).
2. Jalankan perintah:
```powershell
python manage.py loaddata backup_full.json
```

---

## 🛠️ 3. Tips Agar Tidak Error (Orphan Records)

1. **Urutan Import**: Selalu import data **Master** (seperti `core` wilayah) sebelum data **Transaksi** (seperti `perolehan suara`).
2. **Exclude ContentTypes**: Saat backup, selalu gunakan `-e contenttypes -e auth.permission` agar tidak bentrok dengan ID sistem Django yang baru.
3. **Encoding**: Jika muncul error karakter aneh, pastikan terminal bos mendukung UTF-8.

---

## 🗄️ 4. Backup Lewat MySQL (Paling Cepat untuk Data Besar)

Jika data sudah berukuran ratusan MB, lebih baik pakai perintah MySQL langsung:

**Backup:**
```powershell
mysqldump -u root siapa > backup_siapa_mysql.sql
```

**Restore:**
```powershell
mysql -u root siapa < backup_siapa_mysql.sql
```

---
*Dibuat oleh: Antigravity AI khusus untuk SIAPA Project*
