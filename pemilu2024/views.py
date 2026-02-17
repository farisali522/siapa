from django.shortcuts import render
from django.http import JsonResponse
from .models import Kecamatan, KelurahanDesa

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
