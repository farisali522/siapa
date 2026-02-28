import json
from django.http import JsonResponse
from geojson.models import KabupatenGeoJSON, KecamatanGeoJSON
from pilpres_2024.models import PaslonPilpres, KabupatenPilpres, RekapSuaraPilpres

def get_geo_data(request):
    """
    API Utama untuk menyuplai geo_data ke Front-End (Leaflet).
    Format yang dikembalikan adalah murni valid GeoJSON FeatureCollection.
    """
    level = request.GET.get('level', 'kokab')
    mode = request.GET.get('mode', 'all')
    
    features = []

    # 1. AMBIL CACHED AGGREGATE PILPRES JIKA MODE PILPRES
    # 1. AMBIL CACHED AGGREGATE PILPRES JIKA MODE PILPRES
    election_stats = {}
    if mode == 'pilpres':
        paslon_data = list(PaslonPilpres.objects.all().values('id', 'no_urut', 'nama_capres', 'warna_hex'))
        
        if level == 'kokab':
            # Ambil data melalui model proxy yang sudah dioptimasikan with_totals()
            qs_kab = KabupatenPilpres.objects.all().with_totals()
            for obj in qs_kab:
                # obj ini aslinya KabupatenKota dengan added attributes SQL
                dpt = obj.dpt_total or 0
                tps = obj.tps_total or 0
                s1 = obj.s1_total or 0
                s2 = obj.s2_total or 0
                s3 = obj.s3_total or 0
                sah = obj.sah_total or 0
                sts = obj.tidak_sah_total or 0
                
                # Highlight warna paslon menang (untuk color map)
                win_warna = "#808080" # Default abu-abu
                terbesar = -1
                for pd in paslon_data:
                    no_u = pd['no_urut']
                    score = obj.s1_total if no_u == 1 else (obj.s2_total if no_u == 2 else obj.s3_total)
                    if score > terbesar:
                        terbesar = score
                        win_warna = pd['warna_hex']
                # Hitung tingkat rasio kemenangan untuk opacity (Tua = Telak, Pudar = Tipis)
                # Telak (> 60%), Sedang (50% - 60%), Tipis (< 50%)
                fill_opacity = 0.75
                if sah > 0:
                    win_pct = (terbesar / sah) * 100
                    if win_pct > 60:
                        fill_opacity = 0.90  # Tua / Pekat (Telak)
                    elif win_pct >= 50:
                        fill_opacity = 0.65  # Sedang
                    else:
                        fill_opacity = 0.35  # Pudar (Tipis)
                
                election_stats[obj.id] = {
                    's1': s1, 's2': s2, 's3': s3,
                    'sah': sah, 'sts': sts,
                    'tps': tps, 'dpt': dpt,
                    'win_warna': win_warna,
                    'fill_opacity': fill_opacity,
                    'paslon_data': {p['no_urut']: {'nama': p['nama_capres'], 'warna': p['warna_hex']} for p in paslon_data}
                }
                
        elif level == 'kecamatan':
            # Mode Drill-down: Filter berdasarkan Kabupaten tertentu jika ada parameter
            kab_id = request.GET.get('kab_id')
            query = RekapSuaraPilpres.objects.all()
            if kab_id:
                query = query.filter(kecamatan__kabupaten_kota_id=kab_id)
            
            qs_kec = query.with_totals()
            
            for obj in qs_kec:
                try: 
                    tps = obj.kecamatan.tpsdpt_pemilu.jumlah_tps
                    dpt = obj.kecamatan.tpsdpt_pemilu.jumlah_dpt
                except AttributeError: tps = dpt = 0

                s1 = obj.s1 or 0
                s2 = obj.s2 or 0
                s3 = obj.s3 or 0
                sah = obj.total_sah_db or 0
                sts = obj.suara_tidak_sah or 0
                
                win_warna = "#808080"
                terbesar = -1
                for pd in paslon_data:
                    no_u = pd['no_urut']
                    score = obj.s1 if no_u == 1 else (obj.s2 if no_u == 2 else obj.s3)
                    if score > terbesar:
                        terbesar = score
                        win_warna = pd['warna_hex']
                        
                # Hitung tingkat rasio kemenangan untuk opacity (Tua = Telak, Pudar = Tipis)
                # Telak (> 60%), Sedang (50% - 60%), Tipis (< 50%)
                fill_opacity = 0.75
                if sah > 0:
                    win_pct = (terbesar / sah) * 100
                    if win_pct > 60:
                        fill_opacity = 0.90  # Tua / Pekat (Telak)
                    elif win_pct >= 50:
                        fill_opacity = 0.65  # Sedang
                    else:
                        fill_opacity = 0.35  # Pudar (Tipis)

                election_stats[obj.kecamatan.id] = {
                    's1': s1, 's2': s2, 's3': s3,
                    'sah': sah, 'sts': sts,
                    'tps': tps, 'dpt': dpt,
                    'win_warna': win_warna,
                    'fill_opacity': fill_opacity,
                    'paslon_data': {p['no_urut']: {'nama': p['nama_capres'], 'warna': p['warna_hex']} for p in paslon_data}
                }

    elif mode == 'pileg_ri':
        from core.models import Partai
        import pilegri_2024.models as pilegri
        from django.db.models import Sum, OuterRef, Subquery, IntegerField
        from django.db.models.functions import Coalesce

        partai_data_raw = Partai.objects.all().order_by('no_urut')
        partai_data = []
        for pd in partai_data_raw:
            partai_data.append({
                'id': pd.id,
                'no_urut': pd.no_urut,
                'nama': pd.nama,
                'warna_hex': pd.warna_hex,
                'logo_url': pd.logo.url if pd.logo else ''
            })
        
        if level == 'kokab':
            qs_kab = pilegri.KabupatenPilegRI.objects.all()
            
            anns = {}
            for p in partai_data:
                pid = p['id']
                anns[f'p_{pid}_vt'] = Coalesce(Subquery(
                    pilegri.SuaraPartai.objects.filter(rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), partai_id=pid).values('rekap_suara__kecamatan__kabupaten_kota').annotate(t=Sum('jumlah_suara')).values('t'),
                    output_field=IntegerField()
                ), 0) + Coalesce(Subquery(
                    pilegri.DetailSuaraCaleg.objects.filter(rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), caleg__partai_id=pid).values('rekap_suara__kecamatan__kabupaten_kota').annotate(t=Sum('jumlah_suara')).values('t'),
                    output_field=IntegerField()
                ), 0)
            qs_kab = qs_kab.annotate(**anns)
            qs_kab = qs_kab.annotate(
                tps_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_tps'), 0),
                dpt_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_dpt'), 0),
                ts_total=Coalesce(Subquery(
                    pilegri.RekapSuara.objects.filter(kecamatan__kabupaten_kota=OuterRef('pk')).values('kecamatan__kabupaten_kota').annotate(t=Sum('suara_tidak_sah')).values('t'),
                    output_field=IntegerField()
                ), 0)
            )
            
            for obj in qs_kab:
                dpt = obj.dpt_total or 0
                tps = obj.tps_total or 0
                sts = obj.ts_total or 0
                
                win_warna = "#808080"
                terbesar = -1
                sah = 0
                partai_stats_dict = {}
                
                for pd in partai_data:
                    score = getattr(obj, f"p_{pd['id']}_vt", 0)
                    sah += score
                    partai_stats_dict[pd['no_urut']] = {'nama': pd['nama'], 'warna': pd['warna_hex'], 'suara': score, 'logo_url': pd['logo_url']}
                    if score > terbesar:
                        terbesar = score
                        win_warna = pd['warna_hex']
                        
                fill_opacity = 0.75
                if sah > 0:
                    win_pct = (terbesar / sah) * 100
                    if win_pct >= 25: fill_opacity = 0.90
                    elif win_pct >= 15: fill_opacity = 0.65
                    else: fill_opacity = 0.35
                
                election_stats[obj.id] = { 
                    'sah': sah, 'sts': sts,
                    'tps': tps, 'dpt': dpt,
                    'win_warna': win_warna,
                    'fill_opacity': fill_opacity,
                    'partai_data': partai_stats_dict
                }
                
        elif level == 'kecamatan':
            kab_id = request.GET.get('kab_id')
            query = pilegri.RekapSuara.objects.all().select_related('kecamatan__tpsdpt_pemilu')
            if kab_id:
                query = query.filter(kecamatan__kabupaten_kota_id=kab_id)
            
            anns = {}
            for p in partai_data:
                pid = p['id']
                # Suara Partai di RekapSuara ini + Suara Caleg partai di RekapSuara ini
                anns[f'p_{pid}_vt'] = Coalesce(Subquery(
                    pilegri.SuaraPartai.objects.filter(rekap_suara=OuterRef('pk'), partai_id=pid).values('rekap_suara').annotate(t=Sum('jumlah_suara')).values('t'),
                    output_field=IntegerField()
                ), 0) + Coalesce(Subquery(
                    pilegri.DetailSuaraCaleg.objects.filter(rekap_suara=OuterRef('pk'), caleg__partai_id=pid).values('rekap_suara').annotate(t=Sum('jumlah_suara')).values('t'),
                    output_field=IntegerField()
                ), 0)
            qs_kec = query.annotate(**anns)
            
            for obj in qs_kec:
                try: 
                    tps = obj.kecamatan.tpsdpt_pemilu.jumlah_tps
                    dpt = obj.kecamatan.tpsdpt_pemilu.jumlah_dpt
                except AttributeError: tps = dpt = 0

                sts = obj.suara_tidak_sah or 0
                
                win_warna = "#808080"
                terbesar = -1
                sah = 0
                partai_stats_dict = {}
                
                for pd in partai_data:
                    score = getattr(obj, f"p_{pd['id']}_vt", 0)
                    sah += score
                    partai_stats_dict[pd['no_urut']] = {'nama': pd['nama'], 'warna': pd['warna_hex'], 'suara': score, 'logo_url': pd['logo_url']}
                    if score > terbesar:
                        terbesar = score
                        win_warna = pd['warna_hex']
                
                fill_opacity = 0.75
                if sah > 0:
                    win_pct = (terbesar / sah) * 100
                    if win_pct >= 25: fill_opacity = 0.90
                    elif win_pct >= 15: fill_opacity = 0.65
                    else: fill_opacity = 0.35
                
                election_stats[obj.kecamatan.id] = {
                    'sah': sah, 'sts': sts,
                    'tps': tps, 'dpt': dpt,
                    'win_warna': win_warna,
                    'fill_opacity': fill_opacity,
                    'partai_data': partai_stats_dict
                }


    # 2. KONSTRUKSI FEATURES GABUNGAN
    if level == 'kokab':
        geo_qs = KabupatenGeoJSON.objects.select_related('kabupaten').all()
        for g in geo_qs:
            f = g.geojson_data
            
            # Lewati jika data belum ada (None/kosong) karena dibuat manual sbg draft
            if not f: 
                continue
            if isinstance(f, str):
                try: f = json.loads(f)
                except: continue
            if not isinstance(f, dict) or 'properties' not in f:
                continue
            
            kab_id = g.kabupaten.id
            f['properties']['id'] = kab_id
            f['properties']['nama'] = g.kabupaten.nama
            f['properties']['level'] = 'kokab'
            # Default warna abu-abu untuk area yang kosong/mode analisis
            f['properties']['warna'] = '#c0c0c0'
            f['properties']['fill_opacity'] = 0.5
            
            if mode in ['pilpres', 'pileg_ri'] and kab_id in election_stats:
                stat = election_stats[kab_id]
                f['properties'][f'detail_{mode}'] = stat
                f['properties']['warna'] = stat['win_warna']
                f['properties']['fill_opacity'] = stat['fill_opacity']

            features.append(f)
            
    elif level == 'kecamatan':
        kab_id = request.GET.get('kab_id')
        geo_qs = KecamatanGeoJSON.objects.select_related('kecamatan', 'kecamatan__kabupaten_kota').all()
        
        if kab_id:
            geo_qs = geo_qs.filter(kecamatan__kabupaten_kota_id=kab_id)
            
        for g in geo_qs:
            f = g.geojson_data
            
            # Lewati jika data belum ada (None/kosong) karena dibuat manual sbg draft
            if not f: 
                continue
            if isinstance(f, str):
                try: f = json.loads(f)
                except: continue
            if not isinstance(f, dict) or 'properties' not in f:
                continue
                
            kec_id = g.kecamatan.id
            f['properties']['id'] = kec_id
            f['properties']['nama'] = g.kecamatan.nama
            f['properties']['kabupaten'] = g.kecamatan.kabupaten_kota.nama
            f['properties']['level'] = 'kecamatan'
            # Default pola yang sama; abu-abu kalau kosong
            f['properties']['warna'] = '#c0c0c0' 
            f['properties']['fill_opacity'] = 0.5

            if mode in ['pilpres', 'pileg_ri'] and kec_id in election_stats:
                stat = election_stats[kec_id]
                f['properties'][f'detail_{mode}'] = stat
                f['properties']['warna'] = stat['win_warna']
                f['properties']['fill_opacity'] = stat['fill_opacity']

            features.append(f)

    # Return valid FeatureCollection
    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    }, safe=False)
