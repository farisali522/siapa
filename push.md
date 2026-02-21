# Menambahkan semua perubahan (termasuk file gambar rekap baru)
git add .
git commit -m "Update"
git push origin main

# Untuk pengguna Windows (PowerShell)
Compress-Archive -Path media -DestinationPath media.zip

# Untuk pengguna Linux/Mac/Git Bash di Windows
zip -r media.zip media/