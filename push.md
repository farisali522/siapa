# Reset repository
git rm -r --cached .
# Push ke GitHub

git add .
git commit -m "Update"
git push origin main

# Clone pertama kali (jika belum ada foldernya)
git clone https://github.com/farisali522/siapa.git
cd siapa


git pull origin main && source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput && python manage.py loaddata backup_full.json