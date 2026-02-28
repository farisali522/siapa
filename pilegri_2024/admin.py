from django import forms
from django.db import models
from django.contrib import admin
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.http import urlencode
from django.forms.models import modelform_factory
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from collections import OrderedDict
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from import_export.formats.base_formats import XLS

from core.models import Kecamatan, Partai, DapilRI
from .models import Caleg, RekapSuara, DetailSuaraCaleg, KabupatenPilegRI, SuaraPartai, DapilPilegRI

# --- RESOURCES ---
class CalegResource(resources.ModelResource):
    partai = fields.Field(column_name='partai', attribute='partai', widget=widgets.ForeignKeyWidget(Partai, 'nama'))
    dapil = fields.Field(column_name='dapil_ri', attribute='daerah_pemilihan', widget=widgets.ForeignKeyWidget(DapilRI, 'nama'))
    class Meta:
        model = Caleg
        fields = ('id', 'no_urut', 'nama', 'jenis_kelamin', 'partai', 'dapil')

# --- FORM ---
class RekapSuaraForm(forms.ModelForm):
    kecamatan = forms.ModelChoiceField(queryset=Kecamatan.objects.all(), label="Kecamatan", widget=admin.widgets.AutocompleteSelect(RekapSuara._meta.get_field('kecamatan'), admin.site))
    class Meta:
        model = RekapSuara
        fields = ['kecamatan', 'suara_tidak_sah']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Simpan filters dari URL ke hidden field agar tidak hilang saat POST (Save)
            if self.request and self.request.GET:
                self.fields['_preserved_filters'] = forms.CharField(
                    initial=self.request.GET.urlencode(),
                    widget=forms.HiddenInput(),
                    required=False
                )
            
            # Prefetching sakti agar loading form cepat walau calegnya ratusan
            db_inst = RekapSuara.objects.with_totals().select_related(
                'kecamatan__kabupaten_kota__dapil_ri'
            ).prefetch_related(
                'rincian_suara_partai', 'rincian_suara'
            ).get(pk=self.instance.pk)
            fmt = lambda v: "{:,}".format(v).replace(',', '.')
            
            # Cek Filter dari URL
            filter_p = self.request.GET.get('p') if self.request else None
            filter_f = self.request.GET.get('f') if self.request else None

            self.fields['info_kb'] = forms.CharField(label="Kabupaten", initial=db_inst.kecamatan.kabupaten_kota.nama, required=False, disabled=True)
            self.fields['info_dp'] = forms.CharField(label="Dapil RI", initial=db_inst.kecamatan.kabupaten_kota.dapil_ri.nama if db_inst.kecamatan.kabupaten_kota.dapil_ri else "-", required=False, disabled=True)
            self.fields['res_s'] = forms.CharField(label=mark_safe("<b>Total Suara Sah</b>"), initial=fmt(db_inst.t_sah), required=False, disabled=True, widget=forms.TextInput(attrs={'style': 'font-weight:bold; color:#28a745; background:#f8f9fa; border:1px solid #28a745; width:300px;'}))
            self.fields['res_t'] = forms.CharField(label=mark_safe("<b>Total Suara</b>"), initial=fmt(db_inst.t_total), required=False, disabled=True, widget=forms.TextInput(attrs={'style': 'font-weight:bold; color:#007bff; background:#eef6ff; border:1px solid #007bff; width:300px;'}))

            order = OrderedDict()
            
            # Tambahkan link "Reset Filter" jika sedang difilter
            if filter_p or filter_f:
                reset_url = reverse('admin:pilegri_2024_rekapsuara_change', args=[self.instance.pk])
                self.fields['reset_filter'] = forms.CharField(
                    label=mark_safe(
                        f'<div style="background:#fff9e6; border:1px solid #ffeeba; padding:8px 12px; border-radius:6px; margin-bottom:15px; display:inline-flex; align-items:center;">'
                        f'<span style="color:#856404; font-weight:bold; margin-right:15px;">⚠️ MODE FILTER AKTIF</span>'
                        f'<a href="{reset_url}" class="btn btn-sm btn-warning" style="font-weight:bold;">Tampilkan Semua Field (Reset)</a>'
                        f'</div>'
                    ),
                    required=False,
                    disabled=True,
                    widget=forms.HiddenInput()
                )
                order['reset_filter'] = self.fields.pop('reset_filter')

            # --- LOGIKA HIDE FIELD ---
            hide_globals = ['res_s', 'res_t', 'suara_tidak_sah']
            if filter_p: # Jika filter partai, sembunyikan total global & suara tidak sah
                for h in hide_globals:
                    if h in self.fields: self.fields.pop(h)
            
            for k in ['kecamatan', 'info_kb', 'info_dp', 'res_s', 'suara_tidak_sah', 'res_t']:
                if k not in self.fields: continue
                
                # Sembunyikan global totals jika sedang filter partai/sah/ts
                # TAPI tetap tampilkan info wilayah (info_kb/info_dp) untuk konteks rute
                if filter_f == 'ts' and k not in ['info_kb', 'info_dp', 'suara_tidak_sah']:
                    self.fields.pop(k)
                    continue
                if filter_f == 'sah' and k == 'suara_tidak_sah':
                    self.fields.pop(k)
                    continue
                
                order[k] = self.fields.pop(k)

            # --- DATA RINCIAN ---
            p_data = db_inst.rincian_suara_partai.all().values_list('partai_id', 'jumlah_suara')
            c_data = db_inst.rincian_suara.all().values_list('caleg_id', 'jumlah_suara')
            p_ids = dict(p_data)
            c_ids = dict(c_data)
            
            calegs = list(Caleg.objects.filter(daerah_pemilihan=db_inst.kecamatan.kabupaten_kota.dapil_ri).select_related('partai').order_by('partai__no_urut', 'no_urut'))

            # Jika filter Partai, tambahkan Total Suara Partai + Caleg
            if filter_p:
                pid_int = int(filter_p)
                p_obj = Partai.objects.get(id=pid_int)
                p_suara = p_ids.get(pid_int, 0)
                c_suara_total = sum(c_ids.get(c.id, 0) for c in calegs if c.partai_id == pid_int)
                self.fields['res_p_total'] = forms.CharField(
                    label=mark_safe(f"<b>Total Suara {p_obj.nama} (Partai + Caleg)</b>"),
                    initial=fmt(p_suara + c_suara_total),
                    required=False, disabled=True,
                    widget=forms.TextInput(attrs={'style': 'font-weight:bold; color:#e83e8c; background:#fff0f5; border:1px solid #e83e8c; width:300px;'})
                )
                order['res_p_total'] = self.fields.pop('res_p_total')

            for p in Partai.objects.all().order_by('no_urut'):
                # FILTER: Jika ada filter_p, lewatkan partai yang tidak cocok
                if filter_p and str(p.id) != filter_p:
                    continue
                # FILTER: Jika filter_f == 'ts', tidak perlu tampilkan partai sama sekali
                if filter_f == 'ts':
                    break

                f_p = f'su_p_{p.id}'
                logo = format_html('<div style="display:inline-flex; align-items:center; background:#fff; padding:3px; border-radius:4px; border:1px solid #ddd; margin-right:8px; vertical-align:middle;"><img src="{}" style="height:22px;"></div>', p.logo.url) if p.logo else ""
                self.fields[f_p] = forms.IntegerField(label=mark_safe(f"{logo}{p.no_urut}. {p.nama}"), initial=p_ids.get(p.id, 0), required=False, min_value=0, widget=forms.NumberInput(attrs={'style': 'width: 180px; font-weight:bold; border-color: #333;'}))
                order[f_p] = self.fields.pop(f_p)
                for c in [c for c in calegs if c.partai_id == p.id]:
                    f_c = f'su_c_{c.id}'
                    self.fields[f_c] = forms.IntegerField(label=f"└ {c.no_urut}. {c.nama}", initial=c_ids.get(c.id, 0), required=False, min_value=0, widget=forms.NumberInput(attrs={'style': 'width: 180px;'}))
                    order[f_c] = self.fields.pop(f_c)
            self.fields = order

    def save(self, commit=True):
        ins = super().save(commit=commit)
        for n, v in self.cleaned_data.items():
            if n.startswith('su_p_'): SuaraPartai.objects.update_or_create(rekap_suara=ins, partai_id=int(n[5:]), defaults={'jumlah_suara': v or 0})
            if n.startswith('su_c_'): DetailSuaraCaleg.objects.update_or_create(rekap_suara=ins, caleg_id=int(n[5:]), defaults={'jumlah_suara': v or 0})
        return ins

# --- ADMIN ---

@admin.register(Caleg)
class CalegAdmin(ImportExportModelAdmin):
    resource_class = CalegResource
    list_display = ('get_caleg', 'jenis_kelamin', 'daerah_pemilihan', 'get_p')
    list_filter = ('daerah_pemilihan', 'partai')
    search_fields = ('nama',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('partai', 'daerah_pemilihan')

    @admin.display(description='Caleg', ordering='no_urut')
    def get_caleg(self, obj):
        foto = format_html('<div style="background:#fff; padding:2px; border-radius:6px; box-shadow:0 2px 5px rgba(0,0,0,0.1); display:flex; align-items:center; justify-content:center; margin-right:15px; width:45px; height:55px; border:1px solid #ddd;"><img src="{}" style="max-width:100%; max-height:100%; object-fit:cover; border-radius:2px;" /></div>', obj.foto.url) if obj.foto else format_html('<div style="background:#f9f9f9; border-radius:6px; margin-right:15px; width:45px; height:55px; display:flex; align-items:center; justify-content:center; border:1px dashed #ccc; color:#aaa; font-size:9px; text-align:center; line-height:1;">No Photo</div>')
        return format_html('<div style="display:flex; align-items:center; padding:4px 0;"><div style="min-width:24px; height:24px; background:#333; color:#fff; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:11px; margin-right:12px;">{}</div>{} <b>{}</b></div>', obj.no_urut, foto, obj.nama)

    @admin.display(description='Partai')
    def get_p(self, obj):
        if obj.partai.logo: return format_html('<div style="display:flex; align-items:center;"><div style="background:#fff; padding:2px; border-radius:4px; border:1px solid #eee; box-shadow:0 1px 2px rgba(0,0,0,0.1); margin-right:10px; display:flex; width:30px; height:30px; align-items:center; justify-content:center;"><img src="{}" style="max-width:100%; max-height:100%; object-fit:contain;"></div><b>{}</b></div>', obj.partai.logo.url, obj.partai.nama)
        return obj.partai.nama

@admin.register(RekapSuara)
class RekapSuaraAdmin(ImportExportModelAdmin):
    form = RekapSuaraForm
    list_display = ('get_wilayah_dyn',) # Dinamis
    list_display_links = ('get_wilayah_dyn',)
    list_filter = ('kecamatan__kabupaten_kota__dapil_ri', 'kecamatan__kabupaten_kota')
    search_fields = ('kecamatan__nama', 'kecamatan__kabupaten_kota__nama')
    autocomplete_fields = ('kecamatan',)
    ordering = ('kecamatan__kabupaten_kota__dapil_ri__nama', 'kecamatan__kabupaten_kota__nama', 'kecamatan__nama')
    list_per_page = 10
    list_max_show_all = 1000

    def get_wilayah_dyn(self, obj): return ""
    def get_sh_dyn(self, obj): return ""
    def suara_total_tidak_sah_fmt_dyn(self, obj): return ""
    def get_tt_dyn(self, obj): return ""

    def get_list_display(self, request):
        base_query = request.GET.urlencode()

        # --- Dynamic Wilayah Link (ALWAYS RE-CREATE to overwrite stubs) ---
        def _gen_wilayah(obj, bq=base_query):
            content = self.get_wilayah_static(obj)
            url = reverse('admin:pilegri_2024_rekapsuara_change', args=[obj.pk])
            full_url = f"{url}?{bq}".rstrip('?')
            return mark_safe(f'<a href="{full_url}">{content}</a>')
        _gen_wilayah.short_description = 'Wilayah / Dapil'
        _gen_wilayah.admin_order_field = 'kecamatan__nama'
        setattr(self, 'get_wilayah_dyn', _gen_wilayah)

        cols = ['get_wilayah_dyn', 'get_tps_dpt']
        
        # Capture params khusus untuk filter Partai/Sah/Tidak Sah
        p_params = request.GET.copy()
        for k in ['p', 'f']: 
            if k in p_params: p_params.pop(k)
        p_query = p_params.urlencode()
        p_conn = '&' if p_query else ''

        parties = list(Partai.objects.all().order_by('no_urut'))
        for p in parties:
            f_name = f'p_{p.id}_vt'
            p_id, p_name = p.id, p.nama
            p_logo = p.logo.url if p.logo else None
            
            def _gv(obj, pid=p_id, bq=p_query, qc=p_conn):
                v = getattr(obj, f'p_{pid}_vt', 0)
                t_sah = getattr(obj, 't_sah', 0)
                fmt_v = "{:,}".format(v).replace(',', '.')
                
                # Link with PRESERVED FILTERS + PARTY FILTER
                url = reverse('admin:pilegri_2024_rekapsuara_change', args=[obj.pk])
                full_url = f"{url}?{bq}{qc}p={pid}".rstrip('&')
                
                if t_sah > 0:
                    pct = (v / t_sah) * 100
                    p_str = f"({pct:.1f}%)"
                    return format_html(
                        '<div style="text-align:center; min-width:50px;"><a href="{}"><b>{}</b></a><br><small style="color:#666; font-size:9px;">{}</small></div>', 
                        full_url, fmt_v, p_str
                    )
                return format_html('<div style="text-align:center;"><a href="{}">{}</a></div>', full_url, fmt_v)
            
            if p_logo:
                _gv.short_description = mark_safe(
                    f'<div style="text-align:center; min-width:40px;">'
                    f'<img src="{p_logo}" title="{p_name}" style="height:20px; width:20px; object-fit:contain;"><br>'
                    f'<span style="font-size:9px; font-weight:normal; display:block; margin-top:2px;">{p_name}</span>'
                    f'</div>'
                )
            else:
                _gv.short_description = p_name
            
            _gv.admin_order_field = f_name
            setattr(self, f_name, _gv)
            cols.append(f_name)
            
        # Register dynamic helpers for summary columns to preserve filters
        summary_cols = {
            'get_sh': ('sah', 'Suara Sah', 't_sah'), 
            'suara_total_tidak_sah_fmt': ('ts', 'Tidak Sah', 'suara_tidak_sah'), 
            'get_tt': ('', 'Total Suara', 't_total')
        }
        for col_name, (f_val, label, order_field) in summary_cols.items():
            dyn_name = col_name + '_dyn'
            # Closure untuk mengunci variabel per request. Gunakan p_query & p_conn.
            def _create_dyn(fv=f_val, bquery=p_query, qconn=p_conn, static_root=col_name, lbl=label, ord_f=order_field):
                def dynamic_summary(obj):
                    original_method = getattr(self, f'{static_root}_static')
                    original_html = original_method(obj)
                    
                    url = reverse('admin:pilegri_2024_rekapsuara_change', args=[obj.pk])
                    f_param = f"f={fv}" if fv else ""
                    full_url = f"{url}?{bquery}{qconn}{f_param}".rstrip('?&')
                    
                    # Lebih robust: replace href="#" ATAU href="" jika ada
                    html = original_html.replace('href="#"', f'href="{full_url}"')
                    return mark_safe(html.replace('href=""', f'href="{full_url}"'))
                
                dynamic_summary.short_description = lbl
                dynamic_summary.admin_order_field = ord_f
                return dynamic_summary

            setattr(self, dyn_name, _create_dyn())
        
        return cols + ['get_sh_dyn', 'suara_total_tidak_sah_fmt_dyn', 'get_tt_dyn']

    def get_fields(self, request, obj=None):
        if obj:
            # Pass request agar form tahu filter mana yang aktif saat menentukan list field
            form_inst = self.form(instance=obj, request=request)
            return list(form_inst.fields.keys())
        return ['kecamatan', 'suara_tidak_sah']

    def get_form(self, request, obj=None, **kwargs):
        # Inject request ke form agar bisa baca GET param
        if obj:
            # Hanya berikan field model ke modelform_factory agar tidak FieldError
            model_fields = [f.name for f in self.model._meta.get_fields() if not f.is_relation or f.one_to_one or f.many_to_one]
            actual_fields = [f for f in self.get_fields(request, obj) if f in model_fields]
            FormClass = modelform_factory(self.model, form=self.form, fields=actual_fields)
            
            # TRICK: Discover dynamic fields dan tambahkan ke base_fields biar Admin tidak ngamuk FieldError
            dummy = self.form(instance=obj, request=request)
            for f_name, f_obj in dummy.fields.items():
                if f_name not in FormClass.base_fields:
                    FormClass.base_fields[f_name] = f_obj
        else:
            FormClass = super().get_form(request, obj, **kwargs)

        class RequestAdminForm(FormClass):
            def __init__(self, *args, **kwargs):
                kwargs['request'] = request
                super().__init__(*args, **kwargs)
        return RequestAdminForm

    def _preserve_query_params(self, request, response):
        """Helper untuk meneruskan SEMUA parameter (Search, Filter, dll) ke URL redirect."""
        if not isinstance(response, HttpResponseRedirect):
            return response
            
        from django.http import QueryDict
        from urllib.parse import urlparse, urlunparse
        
        # 1. Ambil params. Prioritaskan dari hidden field POST jika ada (saat Save)
        source_params = None
        if '_preserved_filters' in request.POST:
            source_params = QueryDict(request.POST.get('_preserved_filters'), mutable=True)
        
        # 2. Jika POST kosong, ambil dari GET (biasanya dari URL saat ini)
        if not source_params:
            source_params = request.GET.copy()

        if source_params:
            # Bersihkan parameter internal Django agar tidak conflict
            # Kita sisakan _changelist_filters karena ini bawaan Django yang berguna
            for internal_key in ['_save', '_continue', '_addanother']:
                if internal_key in source_params:
                    source_params.pop(internal_key)
            
            if source_params:
                # 3. Ambil URL tujuan redirect
                redirect_url = response['Location']
                parsed = urlparse(redirect_url)
                
                # 4. Gabungkan parameter. Gunakan QueryDict agar aman dengan list/multiple values
                dest_params = QueryDict(parsed.query, mutable=True)
                for key, value_list in source_params.lists():
                    # Timpa atau tambahkan param dari source ke destination
                    dest_params.setlist(key, value_list)
                
                # 5. Rakit kembali URL-nya
                new_query = dest_params.urlencode()
                response['Location'] = urlunparse(parsed._replace(query=new_query))
                
        return response

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)
        return self._preserve_query_params(request, response)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        return self._preserve_query_params(request, response)

    def get_queryset(self, request):
        from django.db.models import Sum, Q, OuterRef, Subquery, IntegerField, F
        from django.db.models.functions import Coalesce
        # select_related & prefetch_related buat ngerem jumlah hit ke DB
        qs = super().get_queryset(request).with_totals().select_related(
            'kecamatan__kabupaten_kota__dapil_ri',
            'kecamatan__tpsdpt_pemilu'
        )
        
        # Cache partai untuk header & annotation
        self._parties = list(Partai.objects.all().order_by('no_urut'))
        
        qs = qs.annotate(
            tps_k=Coalesce(F('kecamatan__tpsdpt_pemilu__jumlah_tps'), 0),
            dpt_k=Coalesce(F('kecamatan__tpsdpt_pemilu__jumlah_dpt'), 0)
        )

        anns = {}
        for p in self._parties:
            anns[f'p_{p.id}_vt'] = Coalesce(Subquery(
                SuaraPartai.objects.filter(rekap_suara=OuterRef('pk'), partai=p).values('jumlah_suara')
            ), 0) + Coalesce(Subquery(
                DetailSuaraCaleg.objects.filter(rekap_suara=OuterRef('pk'), caleg__partai=p).values('rekap_suara').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0)
        return qs.annotate(**anns)

    @admin.display(description='Wilayah / Dapil', ordering='kecamatan__nama')
    def get_wilayah_static(self, obj):
        kab = obj.kecamatan.kabupaten_kota.nama
        dp = obj.kecamatan.kabupaten_kota.dapil_ri.nama if obj.kecamatan.kabupaten_kota.dapil_ri else "-"
        return format_html(
            '<div style="line-height:1.2;"><b>{}</b><br><span style="font-size:10.5px; color:#666;">{} | {}</span></div>',
            obj.kecamatan.nama, kab, dp
        )

    @admin.display(description='TPS / DPT', ordering='tps_k')
    def get_tps_dpt(self, obj):
        return format_html(
            '<div style="line-height:1.2; font-size:11px;">'
            '<span title="Total TPS">TPS: <b>{}</b></span><br>'
            '<span title="Total DPT" style="color:#666;">DPT: {}</span></div>',
            self._fmt(obj.tps_k), self._fmt(obj.dpt_k)
        )

    def _fmt(self, v): return "{:,}".format(v or 0).replace(',', '.')
    @admin.display(description='Suara Sah')
    def get_sh_static(self, obj):
        v, t = obj.t_sah, obj.t_total
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><a href="#"><b>{}</b></a><br><small style="color:#666; font-size:9px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Tidak Sah')
    def suara_total_tidak_sah_fmt_static(self, obj):
        v, t = obj.suara_tidak_sah, obj.t_total
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><a href="#"><b>{}</b></a><br><small style="color:#666; font-size:9px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Total Suara')
    def get_tt_static(self, obj):
        v, d = obj.t_total, obj.dpt_k
        p = f"({(v/d*100):.1f}%)" if d > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><a href="#"><b>{}</b></a><br><small style="color:#007bff; font-weight:bold; font-size:9px;">{}</small></div>', self._fmt(v), p)

@admin.register(DapilPilegRI)
class DapilPilegRIAdmin(admin.ModelAdmin):
    list_display = ('nama',) # Dinamis
    actions = None
    ordering = ('nama',)
    list_per_page = 10
    list_max_show_all = 1000
    
    def get_list_display(self, request):
        cols = ['nama', 'get_tps_dpt']
        self._parties = list(Partai.objects.all().order_by('no_urut'))
        for p in self._parties:
            f_name = f'p_{p.id}_vt'
            if not hasattr(self, f_name):
                p_id, p_name = p.id, p.nama
                p_logo = p.logo.url if p.logo else None
                def _gv(obj, pid=p_id):
                    v = getattr(obj, f'p_{pid}_vt', 0)
                    t_sah = obj.sah_total
                    fmt_v = self._fmt(v)
                    if t_sah > 0:
                        p_str = f"({(v/t_sah*100):.1f}%)"
                        return format_html('<div style="text-align:center; min-width:40px;"><b>{}</b><br><small style="color:#666; font-size:9px;">{}</small></div>', fmt_v, p_str)
                    return format_html('<div style="text-align:center;">{}</div>', fmt_v)
                if p_logo:
                    _gv.short_description = mark_safe(f'<div style="text-align:center;"><img src="{p_logo}" style="height:20px;"><br><span style="font-size:9px;">{p_name}</span></div>')
                else:
                    _gv.short_description = p_name
                setattr(self, f_name, _gv)
            cols.append(f_name)
        return cols + ['get_sah_fmt', 'get_ts_fmt', 'get_tt_fmt']

    def get_queryset(self, request):
        from django.db.models import Sum, OuterRef, Subquery, IntegerField, F
        from django.db.models.functions import Coalesce
        qs = super().get_queryset(request)
        self._parties = list(Partai.objects.all().order_by('no_urut'))
        
        # Annotate dasar level Dapil
        qs = qs.annotate(
            tps_total=Coalesce(Sum('kabupaten_set__kecamatan_set__tpsdpt_pemilu__jumlah_tps'), 0),
            dpt_total=Coalesce(Sum('kabupaten_set__kecamatan_set__tpsdpt_pemilu__jumlah_dpt'), 0),
            ts_total=Coalesce(Subquery(
                RekapSuara.objects.filter(kecamatan__kabupaten_kota__dapil_ri=OuterRef('pk')).values('kecamatan__kabupaten_kota__dapil_ri').annotate(t=Sum('suara_tidak_sah')).values('t'),
                output_field=IntegerField()
            ), 0)
        )
        
        # Annotate party total level Dapil
        anns = {}
        for p in self._parties:
            anns[f'p_{p.id}_vt'] = Coalesce(Subquery(
                SuaraPartai.objects.filter(rekap_suara__kecamatan__kabupaten_kota__dapil_ri=OuterRef('pk'), partai=p).values('rekap_suara__kecamatan__kabupaten_kota__dapil_ri').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0) + Coalesce(Subquery(
                DetailSuaraCaleg.objects.filter(rekap_suara__kecamatan__kabupaten_kota__dapil_ri=OuterRef('pk'), caleg__partai=p).values('rekap_suara__kecamatan__kabupaten_kota__dapil_ri').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0)
        
        qs = qs.annotate(**anns)
        
        # Hitung Sah Total level Dapil
        qs = qs.annotate(
            sah_total=Coalesce(Subquery(
                DetailSuaraCaleg.objects.filter(rekap_suara__kecamatan__kabupaten_kota__dapil_ri=OuterRef('pk')).values('rekap_suara__kecamatan__kabupaten_kota__dapil_ri').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()), 0) + 
                Coalesce(Subquery(SuaraPartai.objects.filter(rekap_suara__kecamatan__kabupaten_kota__dapil_ri=OuterRef('pk')).values('rekap_suara__kecamatan__kabupaten_kota__dapil_ri').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()), 0)
        )
        return qs.annotate(tt_total=F('sah_total') + F('ts_total'))

    def _fmt(self, v): return "{:,}".format(v or 0).replace(',', '.')

    @admin.display(description='TPS / DPT', ordering='tps_total')
    def get_tps_dpt(self, obj):
        return format_html('<div style="font-size:11px;">TPS: <b>{}</b><br><span style="color:#666;">DPT: {}</span></div>', self._fmt(obj.tps_total), self._fmt(obj.dpt_total))

    @admin.display(description='Suara Sah')
    def get_sah_fmt(self, obj):
        p = f"({(obj.sah_total/obj.tt_total*100):.1f}%)" if obj.tt_total > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:9px;">{}</small></div>', self._fmt(obj.sah_total), p)

    @admin.display(description='Tidak Sah')
    def get_ts_fmt(self, obj):
        p = f"({(obj.ts_total/obj.tt_total*100):.1f}%)" if obj.tt_total > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:9px;">{}</small></div>', self._fmt(obj.ts_total), p)

    @admin.display(description='Total Suara')
    def get_tt_fmt(self, obj):
        p = f"({(obj.tt_total/obj.dpt_total*100):.1f}%)" if obj.dpt_total > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#007bff; font-weight:bold; font-size:9px;">{}</small></div>', self._fmt(obj.tt_total), p)
@admin.register(KabupatenPilegRI)
class KabupatenPilegRIAdmin(admin.ModelAdmin):
    list_display = ('nama',) # Dinamis
    actions = None
    ordering = ('nama',)
    list_per_page = 10
    list_max_show_all = 1000
    
    def get_list_display(self, request):
        cols = ['get_kab_dapil', 'get_tps_dpt']
        self._parties = list(Partai.objects.all().order_by('no_urut'))
        for p in self._parties:
            f_name = f'p_{p.id}_vt'
            if not hasattr(self, f_name):
                p_id, p_name = p.id, p.nama
                p_logo = p.logo.url if p.logo else None
                def _gv(obj, pid=p_id):
                    v = getattr(obj, f'p_{pid}_vt', 0)
                    t_sah = obj.sah_total
                    fmt_v = self._fmt(v)
                    if t_sah > 0:
                        p_str = f"({(v/t_sah*100):.1f}%)"
                        return format_html('<div style="text-align:center; min-width:40px;"><b>{}</b><br><small style="color:#666; font-size:9px;">{}</small></div>', fmt_v, p_str)
                    return format_html('<div style="text-align:center;">{}</div>', fmt_v)
                if p_logo:
                    _gv.short_description = mark_safe(f'<div style="text-align:center;"><img src="{p_logo}" style="height:20px;"><br><span style="font-size:9px;">{p_name}</span></div>')
                else:
                    _gv.short_description = p_name
                setattr(self, f_name, _gv)
            cols.append(f_name)
        return cols + ['get_sah_fmt', 'get_ts_fmt', 'get_tt_fmt']

    def get_queryset(self, request):
        from django.db.models import Sum, OuterRef, Subquery, IntegerField, F
        from django.db.models.functions import Coalesce
        qs = super().get_queryset(request).select_related('dapil_ri')
        self._parties = list(Partai.objects.all().order_by('no_urut'))
        
        # Annotate dasar (TPS, DPT, Tidak Sah)
        qs = qs.annotate(
            tps_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_tps'), 0),
            dpt_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_dpt'), 0),
            ts_total=Coalesce(Subquery(
                RekapSuara.objects.filter(kecamatan__kabupaten_kota=OuterRef('pk')).values('kecamatan__kabupaten_kota').annotate(t=Sum('suara_tidak_sah')).values('t'),
                output_field=IntegerField()
            ), 0)
        )
        
        # Annotate party total (Partai + Caleg se-kabupaten)
        anns = {}
        for p in self._parties:
            anns[f'p_{p.id}_vt'] = Coalesce(Subquery(
                SuaraPartai.objects.filter(rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), partai=p).values('rekap_suara__kecamatan__kabupaten_kota').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0) + Coalesce(Subquery(
                DetailSuaraCaleg.objects.filter(rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), caleg__partai=p).values('rekap_suara__kecamatan__kabupaten_kota').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0)
        
        qs = qs.annotate(**anns)
        
        # Hitung Sah Total (Semua partai + Semua caleg)
        qs = qs.annotate(
            sah_total=Coalesce(Subquery(
                DetailSuaraCaleg.objects.filter(rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk')).values('rekap_suara__kecamatan__kabupaten_kota').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()), 0) + 
                Coalesce(Subquery(SuaraPartai.objects.filter(rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk')).values('rekap_suara__kecamatan__kabupaten_kota').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()), 0)
        )
        # Hitung Suara Masuk
        return qs.annotate(tt_total=F('sah_total') + F('ts_total'))

    def _fmt(self, v): return "{:,}".format(v or 0).replace(',', '.')

    @admin.display(description='Kabupaten / Dapil', ordering='nama')
    def get_kab_dapil(self, obj):
        dp = obj.dapil_ri.nama if obj.dapil_ri else "-"
        return format_html(
            '<div style="line-height:1.2;"><b>{}</b><br><span style="font-size:10.5px; color:#666;">{}</span></div>',
            obj.nama, dp
        )

    @admin.display(description='TPS / DPT', ordering='tps_total')
    def get_tps_dpt(self, obj):
        return format_html('<div style="font-size:11px;">TPS: <b>{}</b><br><span style="color:#666;">DPT: {}</span></div>', self._fmt(obj.tps_total), self._fmt(obj.dpt_total))

    @admin.display(description='Suara Sah')
    def get_sah_fmt(self, obj):
        p = f"({(obj.sah_total/obj.tt_total*100):.1f}%)" if obj.tt_total > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:9px;">{}</small></div>', self._fmt(obj.sah_total), p)

    @admin.display(description='Tidak Sah')
    def get_ts_fmt(self, obj):
        p = f"({(obj.ts_total/obj.tt_total*100):.1f}%)" if obj.tt_total > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:9px;">{}</small></div>', self._fmt(obj.ts_total), p)

    @admin.display(description='Total Suara')
    def get_tt_fmt(self, obj):
        p = f"({(obj.tt_total/obj.dpt_total*100):.1f}%)" if obj.dpt_total > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#007bff; font-weight:bold; font-size:9px;">{}</small></div>', self._fmt(obj.tt_total), p)
