from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Kecamatan, KelurahanDesa
from peta.models import GeoKokab, GeoKecamatan, GeoDesKel

def landing(request):
    return render(request, 'landing.html')

from django.views.decorators.cache import never_cache

@never_cache
@login_required
def dashboard_peta(request):
    """Halaman Dashboard Utama untuk menampilkan peta seluruh wilayah"""
    return render(request, 'dashboard_map.html')

@never_cache
@login_required
def dashboard_overview(request):
    """Halaman Dashboard Ringkasan (General)"""
    from django.contrib.admin.models import LogEntry
    
    # Ambil 10 aktivitas terakhir dari LogEntry admin
    recent_actions = LogEntry.objects.select_related('content_type', 'user').order_by('-action_time')[:10]
    
    context = {
        'recent_actions': recent_actions
    }
    return render(request, 'dashboard.html', context)

@login_required
def get_geo_data(request):
    """API untuk mengambil data GeoJSON (Kokab, Kecamatan, Desa)"""
    level = request.GET.get('level', 'kokab')
    mode = request.GET.get('mode', 'default') # mode: default, pilpres
    kab_id = request.GET.get('kab_id')
    kec_id = request.GET.get('kec_id')
    
    features = []
    import json
    
    # --- AMBIL DATA PASLON DARI DB (DINAMIS) ---
    from .models import PaslonPilpres
    paslon_list = PaslonPilpres.objects.all().order_by('no_urut')
    
    # Map data paslon untuk akses cepat
    # Format: {no_urut: {'warna': '#hex', 'nama': 'Anies - Muhaimin', ...}}
    paslon_map = {}
    for p in paslon_list:
        paslon_map[p.no_urut] = {
            'warna': p.warna,
            'nama': f"{p.nama_capres} - {p.nama_cawapres}",
            'foto': p.foto_paslon.url if p.foto_paslon else None
        }

    COLOR_DEFAULT = "#808080" # Abu-abu jika belum ada data/default
    
    # Helper untuk mengatur kepekatan warna berdasarkan persentase kemenangan
    def adjust_color_boldness(hex_color, percentage):
        """
        Mengatur kepekatan warna (Lighter/Darker) berdasarkan persentase kemenangan.
        - > 60%: Solid (Original 100%)
        - 50-60%: Sedang (Campur Putih 30%) - Terlihat bedanya tapi tetap tebal
        - < 50%: Agak Terang (Campur Putih 50%) - Paling muda tapi tidak pucat
        """
        if not hex_color: return "#808080"
        
        # Konversi Hex ke RGB
        hex_color = hex_color.lstrip('#')
        try:
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except:
            return "#808080"
        
        factor = 0
        if percentage >= 60:
            return f"#{hex_color}" # Warna Asli (Solid/Tebal)
        elif percentage >= 50:
            # Agak pudar (Campur putih 30%) - Level Tengah
            factor = 0.3
        else:
            # Sangat pudar (Campur putih 50%) - Level Bawah
            factor = 0.5
            
        new_r = int(r + (255 - r) * factor)
        new_g = int(g + (255 - g) * factor)
        new_b = int(b + (255 - b) * factor)
        
        return f"#{new_r:02x}{new_g:02x}{new_b:02x}"

    try:
        if level == 'kokab':
            geodata = GeoKokab.objects.select_related('kokab').all()
            
            # --- DATA AGREGASI KABUPATEN ---
            from django.db.models import Sum
            from pemilu2024.models import SuaraPilpresKecamatan, RekapTPSDPTKecamatan
            
            rekap_kab = {}
            if mode == 'pilpres':
                # Agregasi Suara
                agg_suara = SuaraPilpresKecamatan.objects.values('kecamatan__kabupaten_kota_id').annotate(
                    ts1=Sum('suara_paslon_1'),
                    ts2=Sum('suara_paslon_2'),
                    ts3=Sum('suara_paslon_3'),
                    tts=Sum('suara_tidak_sah')
                )
                # Agregasi DPT & TPS
                agg_dpt = RekapTPSDPTKecamatan.objects.values('kecamatan__kabupaten_kota_id').annotate(
                    tot_tps=Sum('tps_pemilu'),
                    tot_dpt=Sum('dpt_pemilu')
                )
                
                # Gabung data
                temp_dpt = {x['kecamatan__kabupaten_kota_id']: x for x in agg_dpt}
                
                for item in agg_suara:
                    kid = item['kecamatan__kabupaten_kota_id']
                    dpt_info = temp_dpt.get(kid, {})
                    rekap_kab[kid] = {
                        's1': item['ts1'] or 0,
                        's2': item['ts2'] or 0,
                        's3': item['ts3'] or 0,
                        'sts': item['tts'] or 0,
                        'tps': dpt_info.get('tot_tps', 0) or 0,
                        'dpt': dpt_info.get('tot_dpt', 0) or 0
                    }

            for geo in geodata:
                try:
                    geometry = json.loads(geo.vektor_wilayah)
                    
                    warna = geo.warna_area
                    detail_data = None
                    
                    if mode == 'pilpres':
                        kab_id = geo.kokab.id
                        data = rekap_kab.get(kab_id)
                        
                        if data:
                            s1 = data['s1']
                            s2 = data['s2']
                            s3 = data['s3']
                            sts = data['sts']
                            tps = data['tps']
                            dpt = data['dpt']
                            
                            total_sah = s1 + s2 + s3
                            
                            if total_sah > 0:
                                # Tentukan Warna
                                pemenang = max((s1, 1), (s2, 2), (s3, 3), key=lambda x: x[0])
                                idx_pemenang = pemenang[1]
                                suara_pemenang = pemenang[0]
                                persentase_menang = (suara_pemenang / total_sah) * 100
                                
                                # Ambil warna dari DB Map
                                paslon_info = paslon_map.get(idx_pemenang, {})
                                base_color = paslon_info.get('warna', COLOR_DEFAULT)
                                
                                # Adjust color brightness based on percentage
                                warna = adjust_color_boldness(base_color, persentase_menang)
                                
                                detail_data = {
                                    "s1": s1, "s2": s2, "s3": s3,
                                    "sts": sts, "sah": total_sah,
                                    "tps": tps, "dpt": dpt,
                                    "paslon_data": paslon_map
                                }
                            else:
                                warna = COLOR_DEFAULT
                        else:
                            warna = COLOR_DEFAULT
                        
                    features.append({
                        "type": "Feature",
                        "geometry": geometry.get("geometry", geometry),
                        "properties": {
                            "level": "kokab",
                            "id": geo.kokab.id,
                            "nama": geo.kokab.nama,
                            "warna": warna,
                            "detail_pilpres": detail_data # Kirim Object JSON
                        }
                    })
                except: continue

        elif level == 'kecamatan':
            qs = GeoKecamatan.objects.select_related('kecamatan__kabupaten_kota')
            
            if mode == 'pilpres':
                qs = qs.select_related(
                    'kecamatan__rekap_suara_pilpres_kecamatan',
                    'kecamatan__rekap_tps_dpt_kecamatan'
                )
            
            if kab_id:
                qs = qs.filter(kecamatan__kabupaten_kota_id=kab_id)
            
            for geo in qs:
                try:
                    geometry = json.loads(geo.vektor_wilayah)
                    
                    warna = geo.warna_area
                    detail_data = None
                    
                    if mode == 'pilpres':
                        try:
                            rekap = geo.kecamatan.rekap_suara_pilpres_kecamatan
                            info = geo.kecamatan.rekap_tps_dpt_kecamatan
                            
                            s1 = rekap.suara_paslon_1
                            s2 = rekap.suara_paslon_2
                            s3 = rekap.suara_paslon_3
                            sts = rekap.suara_tidak_sah
                            tps = info.tps_pemilu if info else 0
                            dpt = info.dpt_pemilu if info else 0
                            
                            total_sah = s1 + s2 + s3
                            
                            if total_sah > 0:
                                pemenang = max((s1, 1), (s2, 2), (s3, 3), key=lambda x: x[0])
                                idx_pemenang = pemenang[1]
                                suara_pemenang = pemenang[0]
                                persentase_menang = (suara_pemenang / total_sah) * 100
                                
                                # Ambil warna dari DB Map
                                paslon_info = paslon_map.get(idx_pemenang, {})
                                base_color = paslon_info.get('warna', COLOR_DEFAULT)

                                warna = adjust_color_boldness(base_color, persentase_menang)
                                
                                detail_data = {
                                    "s1": s1, "s2": s2, "s3": s3,
                                    "sts": sts, "sah": total_sah,
                                    "tps": tps, "dpt": dpt,
                                    "paslon_data": paslon_map
                                }
                            else:
                                warna = COLOR_DEFAULT
                        except:
                            warna = COLOR_DEFAULT

                    features.append({
                        "type": "Feature",
                        "geometry": geometry.get("geometry", geometry),
                        "properties": {
                            "level": "kecamatan",
                            "id": geo.kecamatan.id,
                            "nama": f"Kec. {geo.kecamatan.nama}",
                            "kabupaten": geo.kecamatan.kabupaten_kota.nama,
                            "warna": warna,
                            "detail_pilpres": detail_data
                        }
                    })
                except: continue

        elif level == 'desa':
            qs = GeoDesKel.objects.select_related('deskel__kecamatan', 'deskel__kabupaten')
            
            if mode == 'pilpres':
                 qs = qs.select_related('deskel__rekap_suara_pilpres', 'deskel__rekap_tps_dpt')

            if kec_id: qs = qs.filter(deskel__kecamatan_id=kec_id)
            elif kab_id: qs = qs.filter(deskel__kabupaten_id=kab_id)

            for geo in qs:
                try:
                    geometry = json.loads(geo.vektor_wilayah)
                    
                    warna = geo.warna_area
                    detail_data = None
                    
                    if mode == 'pilpres':
                        try:
                            rekap = geo.deskel.rekap_suara_pilpres
                            info = geo.deskel.rekap_tps_dpt
                            
                            s1 = rekap.suara_paslon_1
                            s2 = rekap.suara_paslon_2
                            s3 = rekap.suara_paslon_3
                            sts = rekap.suara_tidak_sah
                            tps = info.tps_pemilu if info else 0
                            dpt = info.dpt_pemilu if info else 0
                            
                            total_sah = s1 + s2 + s3
                            
                            if total_sah > 0:
                                pemenang = max((s1, 1), (s2, 2), (s3, 3), key=lambda x: x[0])
                                idx_pemenang = pemenang[1]
                                suara_pemenang = pemenang[0]
                                persentase_menang = (suara_pemenang / total_sah) * 100
                                
                                # Ambil warna dari DB Map
                                paslon_info = paslon_map.get(idx_pemenang, {})
                                base_color = paslon_info.get('warna', COLOR_DEFAULT)
                                
                                warna = adjust_color_boldness(base_color, persentase_menang)
                                
                                detail_data = {
                                    "s1": s1, "s2": s2, "s3": s3,
                                    "sts": sts, "sah": total_sah,
                                    "tps": tps, "dpt": dpt,
                                    "paslon_data": paslon_map
                                }
                            else:
                                warna = COLOR_DEFAULT
                        except:
                            warna = COLOR_DEFAULT

                    features.append({
                        "type": "Feature",
                        "geometry": geometry.get("geometry", geometry),
                        "properties": {
                            "level": "desa",
                            "id": geo.deskel.id,
                            "nama": f"Desa {geo.deskel.desa_kelurahan}",
                            "kecamatan": geo.deskel.kecamatan.nama,
                            "kabupaten": geo.deskel.kabupaten.nama,
                            "warna": warna,
                            "detail_pilpres": detail_data
                        }
                    })
                except: continue

    except Exception as e:
        print(f"Error getting geo data: {e}")

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

# Login Views
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib import messages

def custom_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard_overview')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard_overview')
        else:
            return render(request, 'login.html', {'error': 'Username atau password salah.'})
            
    return render(request, 'login.html')

def custom_logout(request):
    logout(request)
    return redirect('custom_login')
