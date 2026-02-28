from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from import_export.formats.base_formats import XLS

from core.models import Partai, Kecamatan
from .models import PaslonPilpres, KoalisiPilpres, RekapSuaraPilpres, DetailSuaraPaslon, KabupatenPilpres

# ==============================================================================
# RESOURCES (DATA IMPORT/EXPORT)
# ==============================================================================

class SmartKecamatanWidget(widgets.ForeignKeyWidget):
    """
    Widget kustom untuk mencocokkan nama Kecamatan dari Excel ke Database.
    Mendukung fuzzy matching dan validasi berdasarkan Kabupaten.
    """
    def get_queryset(self, value, row, *args, **kwargs):
        kab_name = row.get('kabupaten', '').strip()
        kec_name = str(value).strip()
        
        qs = self.model.objects.filter(nama__iexact=kec_name)
        if kab_name:
            qs = qs.filter(kabupaten_kota__nama__icontains=kab_name)
        
        if not qs.exists():
            qs = self.model.objects.filter(nama__icontains=kec_name)
            if kab_name:
                qs = qs.filter(kabupaten_kota__nama__icontains=kab_name)
        
        return qs


class RekapSuaraResource(resources.ModelResource):
    """
    Resource untuk penanganan Import/Export data Rekap Suara Pilpres.
    Menghubungkan kolom Excel dengan model RekapSuaraPilpres dan DetailSuaraPaslon.
    """
    kecamatan = fields.Field(
        column_name='kecamatan', 
        attribute='kecamatan', 
        widget=SmartKecamatanWidget(Kecamatan, 'nama')
    )
    kabupaten = fields.Field(
        column_name='kabupaten', 
        attribute='kecamatan__kabupaten_kota__nama', 
        readonly=True
    )
    suara_paslon_1 = fields.Field(column_name='suara_paslon_1')
    suara_paslon_2 = fields.Field(column_name='suara_paslon_2')
    suara_paslon_3 = fields.Field(column_name='suara_paslon_3')

    class Meta:
        model = RekapSuaraPilpres
        fields = ('kabupaten', 'kecamatan', 'suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah')
        import_id_fields = ('kecamatan',)
        skip_unchanged = False
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """Normalisasi header dan data Excel sebelum diproses."""
        for k in list(row.keys()):
            new_k = str(k).lower().strip()
            val = row.pop(k)
            row[new_k] = str(val).strip() if val is not None else ""

    def after_save_instance(self, instance, row, **kwargs):
        """Menyimpan detail perolehan suara paslon setelah data master tersimpan."""
        if not kwargs.get('dry_run', False):
            for no in range(1, 4):
                val = row.get(f'suara_paslon_{no}')
                if val:
                    try:
                        paslon = PaslonPilpres.objects.get(no_urut=no)
                        clean_val = str(val).split('.')[0].replace(',', '').replace('.', '')
                        DetailSuaraPaslon.objects.update_or_create(
                            rekap_suara=instance, 
                            paslon=paslon,
                            defaults={'jumlah_suara': int(clean_val)}
                        )
                    except Exception:
                        pass


# ==============================================================================
# FORMS (CUSTOM ADMIN INTERFACE)
# ==============================================================================

class PaslonPilpresForm(forms.ModelForm):
    """
    Form kustom untuk pengelolaan Paslon.
    Menangani relasi Many-to-Many koalisi dengan widget FilteredSelectMultiple.
    """
    koalisi_pilihan = forms.ModelMultipleChoiceField(
        queryset=Partai.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("Partai Koalisi", is_stacked=False),
        label="Daftar Partai Koalisi"
    )
    class Meta:
        model = PaslonPilpres
        fields = '__all__'
        widgets = {
            'warna_hex': forms.TextInput(attrs={
                'type': 'color', 
                'style': 'width: 150px; height: 45px; border-radius: 4px; cursor: pointer; border: 1px solid #ccc; padding: 2px;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['koalisi_pilihan'].initial = self.instance.koalisi.all()

    def save(self, commit=True):
        instance = super().save(commit=commit)
        KoalisiPilpres.objects.filter(paslon=instance).delete()
        partai_baru = self.cleaned_data.get('koalisi_pilihan')
        if partai_baru:
            for p in partai_baru:
                KoalisiPilpres.objects.create(paslon=instance, partai=p)
        return instance


class UnifiedRekapSuaraForm(forms.ModelForm):
    """
    Form Terpadu untuk input Rekap Suara sekaligus Detail Suara Paslon.
    Menampilkan field dinamis untuk perolehan suara setiap pasangan calon.
    """
    # Definisikan field secara eksplisit agar Django Admin mengenalinya di fieldsets
    tps_target = forms.IntegerField(label="Target TPS", required=False, disabled=True)
    dpt_target = forms.IntegerField(label="Target DPT", required=False, disabled=True)
    
    suara_paslon_1 = forms.IntegerField(label="Suara 01", required=False, min_value=0, widget=forms.NumberInput(attrs={'style': 'width: 200px; font-weight: bold; font-size: 16px; border: 1px solid #000;'}))
    suara_paslon_2 = forms.IntegerField(label="Suara 02", required=False, min_value=0, widget=forms.NumberInput(attrs={'style': 'width: 200px; font-weight: bold; font-size: 16px; border: 1px solid #000;'}))
    suara_paslon_3 = forms.IntegerField(label="Suara 03", required=False, min_value=0, widget=forms.NumberInput(attrs={'style': 'width: 200px; font-weight: bold; font-size: 16px; border: 1px solid #000;'}))

    class Meta:
        model = RekapSuaraPilpres
        fields = ['kecamatan', 'suara_tidak_sah']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ambil data pembanding TPS/DPT dari core
        if self.instance.pk and hasattr(self.instance.kecamatan, 'tpsdpt_pemilu'):
            tps_data = self.instance.kecamatan.tpsdpt_pemilu
            self.fields['tps_target'].initial = tps_data.jumlah_tps
            self.fields['dpt_target'].initial = tps_data.jumlah_dpt

        # Update label dinamis jika perlu dan set nilai awal
        paslons = PaslonPilpres.objects.all().order_by('no_urut')
        details_map = {}
        if self.instance.pk:
            details = DetailSuaraPaslon.objects.filter(rekap_suara=self.instance)
            details_map = {d.paslon_id: d.jumlah_suara for d in details}

        for paslon in paslons:
            field_name = f'suara_paslon_{paslon.no_urut}'
            if field_name in self.fields:
                self.fields[field_name].label = f"Suara 0{paslon.no_urut}. {paslon.nama_capres}"
                self.fields[field_name].initial = details_map.get(paslon.id, 0)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        paslons = PaslonPilpres.objects.all()
        for paslon in paslons:
            field_name = f'suara_paslon_{paslon.no_urut}'
            val = self.cleaned_data.get(field_name, 0)
            DetailSuaraPaslon.objects.update_or_create(
                rekap_suara=instance, paslon=paslon, defaults={'jumlah_suara': val}
            )
        return instance


# ==============================================================================
# ADMIN CONFIGURATIONS (LIST VIEWS & OPTIMIZATIONS)
# ==============================================================================

@admin.register(PaslonPilpres)
class PaslonPilpresAdmin(admin.ModelAdmin):
    """Konfigurasi Admin untuk entitas Pasangan Calon Pilpres."""
    form = PaslonPilpresForm
    list_display = ('paslon_info', 'color_preview', 'get_koalisi_logos', 'total_suara_diperoleh')
    ordering = ('no_urut',)

    def get_queryset(self, request):
        return super().get_queryset(request).with_totals()

    @admin.display(description='Pasangan Calon')
    def paslon_info(self, obj):
        foto_html = ""
        if obj.foto_paslon:
            foto_html = format_html(
                '<div style="background: #fff; padding: 2px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.15); '
                'display: flex; align-items: center; justify-content: center; margin-right: 15px; width: 100px; height: 70px; border: 1px solid #ddd;">'
                '<img src="{}" style="max-width: 100%; max-height: 100%; object-fit: contain;" />'
                '</div>', obj.foto_paslon.url
            )
        return format_html(
            '<div style="display: flex; align-items: center; padding: 4px 0;">'
            '<div style="min-width: 30px; height: 30px; background: #333; color: #fff; border-radius: 50%; '
            'display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; '
            'margin-right: 15px;">{}</div>'
            '{} <b>{} - {}</b></div>', obj.no_urut, foto_html, obj.nama_capres, obj.nama_cawapres
        )

    @admin.display(description='Koalisi Pendukung')
    def get_koalisi_logos(self, obj):
        logos = "".join([format_html(
            '<img src="{}" title="{}" style="width: 35px; height: 35px; object-fit: contain; margin-right: 8px; '
            'background: #fff; padding: 2px; border-radius: 4px; border: 1px solid #eee; box-shadow: 0 1px 3px rgba(0,0,0,0.1);" />', 
            p.logo.url, p.nama
        ) for p in obj.koalisi.all() if p.logo])
        return format_html('<div style="display: flex; align-items: center;">{}</div>', format_html(logos)) if logos else "-"

    @admin.display(description='Warna Identitas')
    def color_preview(self, obj):
        return format_html(
            '<div style="display: flex; align-items: center; background: #f8f9fa; padding: 4px 10px; border-radius: 20px; border: 1px solid #ddd; width: fit-content;">'
            '<div style="width: 14px; height: 14px; background: {}; border-radius: 50%; margin-right: 8px; border: 1.5px solid #fff; box-shadow: 0 0 0 1px #ddd;"></div>'
            '<span style="font-family: Courier; font-weight: bold;">{}</span></div>',
            obj.warna_hex, obj.warna_hex
        )

    # Caching untuk request saat ini agar tidak hit DB looping
    _total_sah_cache = None
    _win_stats_cache = None

    def _get_global_stats(self):
        """Menghitung total sah & sebaran kemenangan sekali saja per request list."""
        if self._total_sah_cache is None:
            from django.db.models import Sum, Max, F
            from .models import DetailSuaraPaslon, RekapSuaraPilpres
            
            # 1. Total Suara Nasional
            res = DetailSuaraPaslon.objects.aggregate(t=Sum('jumlah_suara'))
            self._total_sah_cache = res['t'] or 0
            
            # 2. Hitung Kemenangan per Kecamatan
            # Ambil semua data rincian
            details_kec = DetailSuaraPaslon.objects.values('rekap_suara_id', 'paslon_id', 'jumlah_suara')
            
            rekap_map_kec = {} # rekap_id -> {paslon_id: suara}
            for d in details_kec:
                rid = d['rekap_suara_id']
                pid = d['paslon_id']
                suara = d['jumlah_suara']
                if rid not in rekap_map_kec: rekap_map_kec[rid] = {}
                rekap_map_kec[rid][pid] = suara
                
            win_kec_counts = {} # paslon_id -> count win
            for rid, pid_votes in rekap_map_kec.items():
                if pid_votes:
                    win_pid = max(pid_votes, key=pid_votes.get)
                    win_kec_counts[win_pid] = win_kec_counts.get(win_pid, 0) + 1
                    
            # 3. Hitung Kemenangan per Kabupaten
            # Group by kabupaten
            details_kab = DetailSuaraPaslon.objects.values(
                'rekap_suara__kecamatan__kabupaten_kota_id', 'paslon_id'
            ).annotate(total=Sum('jumlah_suara'))
            
            rekap_map_kab = {}
            for d in details_kab:
                kab_id = d['rekap_suara__kecamatan__kabupaten_kota_id']
                pid = d['paslon_id']
                suara = d['total']
                if kab_id not in rekap_map_kab: rekap_map_kab[kab_id] = {}
                rekap_map_kab[kab_id][pid] = suara
                
            win_kab_counts = {}
            for kab_id, pid_votes in rekap_map_kab.items():
                if pid_votes:
                    win_pid = max(pid_votes, key=pid_votes.get)
                    win_kab_counts[win_pid] = win_kab_counts.get(win_pid, 0) + 1
            
            self._win_stats_cache = {'kec': win_kec_counts, 'kab': win_kab_counts}

    @admin.display(description='Statistik', ordering='total_suara')
    def total_suara_diperoleh(self, obj):
        self._get_global_stats()
        
        total = obj.total_suara or 0
        total_sah = self._total_sah_cache
        
        pct = f"{(total/total_sah*100):.1f}%" if total_sah > 0 else "0.0%"
        fmt_total = "{:,}".format(total).replace(',', '.')
        
        win_kec = self._win_stats_cache['kec'].get(obj.id, 0)
        win_kab = self._win_stats_cache['kab'].get(obj.id, 0)

        return format_html(
            '<div style="min-width: 250px;">'
            '<div style="font-size: 16px; font-weight: 700; color: #28a745; background: #e8f5e9; '
            'padding: 8px 12px; border-radius: 6px; border: 1px solid #c8e6c9; display: flex; align-items: center; justify-content: space-between; margin-bottom:6px;">'
            '<span>{} <span style="font-size: 11px; font-weight: normal; color: #666;">suara</span></span>'
            '<span style="background: #fff; color: #155724; padding: 2px 6px; border-radius: 4px; font-size: 13px; border: 1px solid #c8e6c9;">{}</span>'
            '</div>'
            '<div style="font-size: 11.5px; color: #495057; background: #f8f9fa; padding: 5px 8px; border-radius: 4px; border: 1px solid #ddd; line-height: 1.4;">'
            'Menang di <b>{}</b> Kabupaten/Kota<br>'
            'Menang di <b>{}</b> Kecamatan'
            '</div>'
            '</div>',
            fmt_total, pct, win_kab, win_kec
        )


@admin.register(RekapSuaraPilpres)
class RekapSuaraAdmin(ImportExportModelAdmin):
    """
    Admin perolehan suara Pilpres.
    Dilengkapi dengan optimasi SQL kustom untuk performa tinggi pada list view.
    """
    form = UnifiedRekapSuaraForm
    resource_class = RekapSuaraResource
    formats = (XLS,)
    list_display = (
        'get_wilayah_dyn', 'get_tps_dpt',
        'suara_paslon_1_fmt', 'suara_paslon_2_fmt', 'suara_paslon_3_fmt',
        'total_suara_sah_fmt', 'suara_tidak_sah_fmt', 'total_suara_masuk_fmt'
    )
    list_display_links = ('get_wilayah_dyn',)
    list_filter = ('kecamatan__kabupaten_kota',)
    autocomplete_fields = ('kecamatan',)
    ordering = ('kecamatan__kabupaten_kota__nama', 'kecamatan__nama')
    
    # SATU HALAMAN: Semua field tampil sekaligus tanpa pembatas
    fields = ('kecamatan', 'tps_target', 'dpt_target', 'suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah')

    @admin.display(description='Wilayah', ordering='kecamatan__nama')
    def get_wilayah_dyn(self, obj):
        kab = obj.kecamatan.kabupaten_kota.nama
        return format_html(
            '<div style="line-height:1.2;"><b>{}</b><br><span style="font-size:10.5px; color:#666;">{}</span></div>',
            obj.kecamatan.nama, kab
        )
        
    def changelist_view(self, request, extra_context=None):
        """Update header kolom secara dinamis berdasarkan data Paslon terbaru."""
        from .models import PaslonPilpres
        paslons = {p.no_urut: p.foto_paslon.url for p in PaslonPilpres.objects.all() if p.foto_paslon}
        
        for no in range(1, 4):
            method_name = f'suara_paslon_{no}_fmt'
            # Kita ambil langsung function-nya dari class (unbound method)
            # karena admin.display merubah property di function tersebut
            method = getattr(self.__class__, method_name, None)
            if method and no in paslons:
                # Bypass properti method dengan men-set short_description
                method.short_description = format_html(
                    '0{} <br> <img src="{}" style="width:45px;height:45px;object-fit:contain;border-radius:4px;border:1px solid #ddd;padding:2px;background:#fff;margin-top:4px;">', 
                    no, paslons[no]
                )
        return super().changelist_view(request, extra_context)

    def get_queryset(self, request):
        """Optimasi penarikan data relasi dan perhitungan agregat di level SQL sudah ditarik ke model layer."""
        return super().get_queryset(request).with_totals()

    def _fmt(self, val):
        """Helper untuk format angka Indonesia (titik sebagai ribuan)."""
        return "{:,}".format(val or 0).replace(',', '.')

    @admin.display(description='TPS / DPT', ordering='kecamatan__tpsdpt_pemilu__jumlah_tps')
    def get_tps_dpt(self, obj):
        tps = obj.kecamatan.tpsdpt_pemilu.jumlah_tps if hasattr(obj.kecamatan, 'tpsdpt_pemilu') else 0
        dpt = obj.kecamatan.tpsdpt_pemilu.jumlah_dpt if hasattr(obj.kecamatan, 'tpsdpt_pemilu') else 0
        return format_html(
            '<div style="line-height:1.2; font-size:11px;">'
            '<span title="Total TPS">TPS: <b>{}</b></span><br>'
            '<span title="Total DPT" style="color:#666;">DPT: {}</span></div>',
            self._fmt(tps), self._fmt(dpt)
        )

    @admin.display(description='(01)', ordering='s1')
    def suara_paslon_1_fmt(self, obj):
        v = obj.s1 or 0
        t = obj.total_sah_db or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='(02)', ordering='s2')
    def suara_paslon_2_fmt(self, obj):
        v = obj.s2 or 0
        t = obj.total_sah_db or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='(03)', ordering='s3')
    def suara_paslon_3_fmt(self, obj):
        v = obj.s3 or 0
        t = obj.total_sah_db or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Total Sah', ordering='total_sah_db')
    def total_suara_sah_fmt(self, obj):
        v = obj.total_sah_db or 0
        t = getattr(obj, 'total_masuk_db', v + (obj.suara_tidak_sah or 0)) or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Tidak Sah', ordering='suara_tidak_sah')
    def suara_tidak_sah_fmt(self, obj):
        v = obj.suara_tidak_sah or 0
        t = getattr(obj, 'total_masuk_db', (obj.total_sah_db or 0) + v) or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Total Suara', ordering='total_masuk_db')
    def total_suara_masuk_fmt(self, obj):
        v = getattr(obj, 'total_masuk_db', getattr(obj, 'total_suara_masuk', 0)) or 0
        d = obj.kecamatan.tpsdpt_pemilu.jumlah_dpt if hasattr(obj.kecamatan, 'tpsdpt_pemilu') else 0
        p = f"({(v/d*100):.1f}%)" if d > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#007bff; font-weight:bold; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    def get_export_filename(self, request, file_format, queryset, **kwargs):
        ext = file_format.get_extension() if file_format else "xls"
        return f"rekap_suara_pilpres_2024.{ext}"


@admin.register(KabupatenPilpres)
class KabupatenPilpresAdmin(admin.ModelAdmin):
    """
    Admin proxy untuk menampilkan data Pilpres pada tingkat Kabupaten/Kota.
    Optimasi: Menggunakan agregat SQL untuk menghitung total suara dari semua kecamatan.
    """
    list_display = (
        'nama', 'get_tps_dpt', 
        'suara_1_fmt', 'suara_2_fmt', 'suara_3_fmt',
        'total_suara_sah_fmt', 'suara_tidak_sah_fmt', 'total_suara_masuk_fmt'
    )

    def get_queryset(self, request):
        return super().get_queryset(request).with_totals()

    def changelist_view(self, request, extra_context=None):
        """Update header kolom secara dinamis berdasarkan data Paslon terbaru."""
        from .models import PaslonPilpres
        paslons = {p.no_urut: p.foto_paslon.url for p in PaslonPilpres.objects.all() if p.foto_paslon}
        
        for no in range(1, 4):
            method_name = f'suara_{no}_fmt'
            method = getattr(self.__class__, method_name, None)
            if method and no in paslons:
                method.short_description = format_html(
                    '0{} <br> <img src="{}" style="width:45px;height:45px;object-fit:contain;border-radius:4px;border:1px solid #ddd;padding:2px;background:#fff;margin-top:4px;">', 
                    no, paslons[no]
                )
        return super().changelist_view(request, extra_context)

    def _fmt(self, val):
        return "{:,}".format(val or 0).replace(',', '.')

    @admin.display(description='TPS / DPT', ordering='tps_total')
    def get_tps_dpt(self, obj):
        return format_html(
            '<div style="line-height:1.2; font-size:11px;">'
            '<span title="Total TPS">TPS: <b>{}</b></span><br>'
            '<span title="Total DPT" style="color:#666;">DPT: {}</span></div>',
            self._fmt(obj.tps_total), self._fmt(obj.dpt_total)
        )

    @admin.display(description='(01)', ordering='s1_total')
    def suara_1_fmt(self, obj):
        v = obj.s1_total or 0
        t = obj.sah_total or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='(02)', ordering='s2_total')
    def suara_2_fmt(self, obj):
        v = obj.s2_total or 0
        t = obj.sah_total or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='(03)', ordering='s3_total')
    def suara_3_fmt(self, obj):
        v = obj.s3_total or 0
        t = obj.sah_total or 0
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Total Sah', ordering='sah_total')
    def total_suara_sah_fmt(self, obj):
        v = obj.sah_total or 0
        t = getattr(obj, 'total_masuk', (obj.sah_total or 0) + (obj.tidak_sah_total or 0)) 
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Tidak Sah', ordering='tidak_sah_total')
    def suara_tidak_sah_fmt(self, obj):
        v = obj.tidak_sah_total or 0
        t = getattr(obj, 'total_masuk', (obj.sah_total or 0) + (obj.tidak_sah_total or 0))
        p = f"({(v/t*100):.1f}%)" if t > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#666; font-size:11.5px;">{}</small></div>', self._fmt(v), p)

    @admin.display(description='Total Suara', ordering='total_masuk_db')
    def total_suara_masuk_fmt(self, obj):
        v = (obj.sah_total or 0) + (obj.tidak_sah_total or 0)
        d = obj.dpt_total or 0
        p = f"({(v/d*100):.1f}%)" if d > 0 else "(0.0%)"
        return format_html('<div style="text-align:center;"><b>{}</b><br><small style="color:#007bff; font-weight:bold; font-size:11.5px;">{}</small></div>', self._fmt(v), p)
