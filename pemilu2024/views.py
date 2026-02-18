from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Kecamatan, KelurahanDesa, GeoKokab

def landing(request):
    return render(request, 'landing.html')

@login_required
def dashboard_peta(request):
    """Halaman Dashboard Utama untuk menampilkan peta seluruh wilayah"""
    return render(request, 'dashboard_map.html')

@login_required
def get_geo_data(request):
    """API untuk mengambil semua data GeoJSON Kabupaten/Kota"""
    geodata = GeoKokab.objects.select_related('kokab').all()
    features = []
    
    import json
    for geo in geodata:
        try:
            # Parse GeoJSON string back to dict
            geometry = json.loads(geo.vektor_wilayah)
            
            # Gabungkan dengan data suara (dummy dulu atau ambil rekap)
            # Nanti bisa ditambahin logic rekap suara di sini
            
            feature = {
                "type": "Feature",
                "geometry": geometry.get("geometry", geometry), # Handle both Feature and Geometry
                "properties": {
                    "nama": geo.kokab.nama,
                    "warna": geo.warna_area,
                    # Nanti bisa tambah data statistik di sini
                }
            }
            features.append(feature)
        except:
            continue
            
    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    })

def get_kecamatan(request):
    kabupaten_id = request.GET.get('kabupaten_id')
    kecamatans = Kecamatan.objects.filter(kabupaten_kota_id=kabupaten_id).order_by('nama')
    data = [{'id': k.id, 'nama': k.nama} for k in kecamatans]
    return JsonResponse(data, safe=False)

def get_desa(request):
    kecamatan_id = request.GET.get('kecamatan_id')
    desas = KelurahanDesa.objects.filter(kecamatan_id=kecamatan_id).order_by('desa_kelurahan')
    data = [{'id': d.id, 'nama': d.desa_kelurahan} for d in desas]
    return JsonResponse(data, safe=False)
