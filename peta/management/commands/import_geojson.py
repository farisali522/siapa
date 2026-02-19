import json
import os
from django.core.management.base import BaseCommand
from django.db.models import Q
from pemilu2024.models import Kecamatan, KabupatenKota, KelurahanDesa
from peta.models import GeoKecamatan, GeoKokab, GeoDesKel

class Command(BaseCommand):
    help = 'Import GeoJSON polygons to database (support Kokab, Kecamatan, Desa)'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to GeoJSON file')
        parser.add_argument(
            '--level', 
            type=str, 
            help='Level data: kokab, kecamatan, or desa',
            choices=['kokab', 'kecamatan', 'desa'],
            required=True
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        level = kwargs['level']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        self.stdout.write(f'Reading GeoJSON file: {file_path} ...')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Invalid JSON format: {e}'))
            return

        features = data.get('features', [])
        total = len(features)
        success = 0
        failed = 0
        
        self.stdout.write(f'Total Features found: {total}')
        self.stdout.write('Starting import process...\n')

        for idx, feat in enumerate(features, 1):
            props = feat.get('properties', {})
            geometry = feat.get('geometry')
            
            if not geometry:
                self.stdout.write(self.style.WARNING(f'Skipping feature #{idx}: No geometry'))
                continue

            # --- LOGIC IMPORT PER LEVEL ---
            
            # 1. KECAMATAN
            if level == 'kecamatan':
                nama_kec = props.get('KECAMATAN') or props.get('kecamatan') or props.get('NAMOBJ')
                nama_kab = props.get('KABKOT') or props.get('kabkot') or props.get('KABUPATEN')
                
                if not nama_kec:
                    self.stdout.write(self.style.WARNING(f'Skipping #{idx}: Missing "kecamatan" property'))
                    failed += 1
                    continue

                # Cari Kecamatan di Database
                clean_kec = nama_kec.upper().replace("KEC.", "").strip()
                qs = Kecamatan.objects.filter(nama__iexact=clean_kec)
                
                if nama_kab:
                    clean_kab = nama_kab.upper().replace("KAB.", "").replace("KOTA", "").strip()
                    qs = qs.filter(kabupaten_kota__nama__icontains=clean_kab)
                
                target_obj = qs.first()

                if target_obj:
                    # Simpan ke GeoKecamatan
                    geo_obj, created = GeoKecamatan.objects.get_or_create(kecamatan=target_obj)
                    
                    geo_data = {
                        "type": "Feature",
                        "properties": {
                            "name": target_obj.nama,
                            "kab": target_obj.kabupaten_kota.nama
                        },
                        "geometry": geometry
                    }
                    geo_obj.vektor_wilayah = json.dumps(geo_data)
                    geo_obj.save()
                    status = "CREATED" if created else "UPDATED"
                    self.stdout.write(self.style.SUCCESS(f'[{status}] {target_obj.nama} ({target_obj.kabupaten_kota.nama})'))
                    success += 1
                else:
                    self.stdout.write(self.style.ERROR(f'[NOT FOUND] Kec: {nama_kec} | Kab: {nama_kab}'))
                    failed += 1

            # 2. KABUPATEN / KOTA
            elif level == 'kokab':
                nama_kab = props.get('KABKOT') or props.get('kabkot') or props.get('KAB_KOTA') or props.get('NAMOBJ')
                
                if not nama_kab:
                    self.stdout.write(self.style.WARNING(f'Skipping #{idx}: Missing "kabkot" property'))
                    failed += 1
                    continue
                    
                clean_kab = nama_kab.upper().replace("KAB.", "").replace("KOTA", "").strip()
                
                # Cari KabupatenKota
                target_obj = KabupatenKota.objects.filter(nama__icontains=clean_kab).first()

                if target_obj:
                    geo_obj, created = GeoKokab.objects.get_or_create(kokab=target_obj)
                    
                    geo_data = {
                        "type": "Feature",
                        "properties": {"name": target_obj.nama},
                        "geometry": geometry
                    }
                    geo_obj.vektor_wilayah = json.dumps(geo_data)
                    geo_obj.save()
                    status = "CREATED" if created else "UPDATED"
                    self.stdout.write(self.style.SUCCESS(f'[{status}] {target_obj.nama}'))
                    success += 1
                else:
                    self.stdout.write(self.style.ERROR(f'[NOT FOUND] Kab/Kota: {nama_kab}'))
                    failed += 1

            # 3. DESA / KELURAHAN
            elif level == 'desa':
                nama_desa = props.get('DESA') or props.get('desa') or props.get('NAMOBJ')
                nama_kec = props.get('KECAMATAN') or props.get('kecamatan') or props.get('WADMKC')

                
                if not nama_desa:
                    self.stdout.write(self.style.WARNING(f'Skipping #{idx}: Missing "desa" property'))
                    failed += 1
                    continue
                
                clean_desa = nama_desa.upper().replace("DESA", "").replace("KEL.", "").strip()
                
                qs = KelurahanDesa.objects.filter(desa_kelurahan__iexact=clean_desa)
                
                if nama_kec:
                   clean_kec = nama_kec.upper().replace("KEC.", "").strip()
                   qs = qs.filter(kecamatan__nama__iexact=clean_kec)
                
                target_obj = qs.first()

                if target_obj:
                    geo_obj, created = GeoDesKel.objects.get_or_create(deskel=target_obj)
                    
                    geo_data = {
                        "type": "Feature",
                        "properties": {
                            "name": target_obj.desa_kelurahan,
                            "kec": target_obj.kecamatan.nama
                        },
                        "geometry": geometry
                    }
                    
                    geo_obj.vektor_wilayah = json.dumps(geo_data)
                    geo_obj.save()
                    
                    status = "CREATED" if created else "UPDATED"
                    self.stdout.write(self.style.SUCCESS(f'[{status}] {target_obj.desa_kelurahan} ({target_obj.kecamatan.nama})'))
                    success += 1
                else:
                    self.stdout.write(self.style.ERROR(f'[NOT FOUND] Desa: {nama_desa} | Kec: {nama_kec}'))
                    failed += 1

        self.stdout.write('\n' + '='*40)
        self.stdout.write(f'DONE. Success: {success}, Failed: {failed}, Total: {total}')
