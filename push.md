# Menambahkan semua perubahan (termasuk file gambar rekap baru)
git add .

# Memberikan pesan komit (Haji bisa ubah pesannya sesuai kebutuhan)
git commit -m "Update"

# Mengirim data ke server (Master/Main)
git push origin main

# Memastikan repositori lokal di VPS mengenali perubahan di server
git fetch origin

# Menarik data terbaru dari branch main ke VPS
git pull origin main

# Jika ada perubahan model database
python manage.py migrate

# Jika ada perubahan file CSS/JS/Gambar
python manage.py collectstatic --noinput