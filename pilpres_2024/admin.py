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
    list_display = ('paslon_info', 'color_preview', 'get_koalisi_logos')
    ordering = ('no_urut',)

    def get_queryset(self, request):
        # OPTIMASI: Prefetch koalisi agar logo partai tidak hit DB berkali-kali
        return super().get_queryset(request).prefetch_related('koalisi')

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
        'get_kabupaten', 'kecamatan', 'get_tps', 'get_dpt',
        'suara_paslon_1_fmt', 'suara_paslon_2_fmt', 'suara_paslon_3_fmt',
        'total_suara_sah_fmt', 'suara_tidak_sah_fmt', 'total_suara_masuk_fmt'
    )
    list_filter = ('kecamatan__kabupaten_kota',)
    autocomplete_fields = ('kecamatan',)
    
    # SATU HALAMAN: Semua field tampil sekaligus tanpa pembatas
    fields = ('kecamatan', 'tps_target', 'dpt_target', 'suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah')

    def changelist_view(self, request, extra_context=None):
        """Update header kolom secara dinamis berdasarkan data Paslon terbaru."""
        from .models import PaslonPilpres
        paslons = {p.no_urut: p.foto_paslon.url for p in PaslonPilpres.objects.all() if p.foto_paslon}
        
        for no in range(1, 4):
            method_name = f'suara_paslon_{no}_fmt'
            method = getattr(self, method_name, None)
            if method and no in paslons:
                method.description = format_html(
                    '0{} <br> <img src="{}" style="width:25px;height:25px;border-radius:3px;border:1px solid #ddd;padding:1px;background:#fff;">', 
                    no, paslons[no]
                )
        return super().changelist_view(request, extra_context)

    def get_queryset(self, request):
        """Optimasi penarikan data relasi dan perhitungan agregat di level SQL."""
        qs = super().get_queryset(request)
        from django.db.models import Sum, F, Q
        return qs.select_related(
            'kecamatan', 'kecamatan__kabupaten_kota', 'kecamatan__tpsdpt_pemilu'
        ).annotate(
            total_sah_db=Sum('rincian_suara__jumlah_suara'),
            total_masuk_db=Sum('rincian_suara__jumlah_suara') + F('suara_tidak_sah'),
            s1=Sum('rincian_suara__jumlah_suara', filter=Q(rincian_suara__paslon__no_urut=1)),
            s2=Sum('rincian_suara__jumlah_suara', filter=Q(rincian_suara__paslon__no_urut=2)),
            s3=Sum('rincian_suara__jumlah_suara', filter=Q(rincian_suara__paslon__no_urut=3)),
        )

    def _fmt(self, val):
        """Helper untuk format angka Indonesia (titik sebagai ribuan)."""
        return "{:,}".format(val or 0).replace(',', '.')

    @admin.display(description='Kabupaten/Kota', ordering='kecamatan__kabupaten_kota')
    def get_kabupaten(self, obj):
        return obj.kecamatan.kabupaten_kota.nama

    @admin.display(description='TPS', ordering='kecamatan__tpsdpt_pemilu__jumlah_tps')
    def get_tps(self, obj):
        val = obj.kecamatan.tpsdpt_pemilu.jumlah_tps if hasattr(obj.kecamatan, 'tpsdpt_pemilu') else 0
        return self._fmt(val)

    @admin.display(description='DPT', ordering='kecamatan__tpsdpt_pemilu__jumlah_dpt')
    def get_dpt(self, obj):
        val = obj.kecamatan.tpsdpt_pemilu.jumlah_dpt if hasattr(obj.kecamatan, 'tpsdpt_pemilu') else 0
        return self._fmt(val)

    @admin.display(description='(01)', ordering='s1')
    def suara_paslon_1_fmt(self, obj):
        return self._fmt(obj.s1)

    @admin.display(description='(02)', ordering='s2')
    def suara_paslon_2_fmt(self, obj):
        return self._fmt(obj.s2)

    @admin.display(description='(03)', ordering='s3')
    def suara_paslon_3_fmt(self, obj):
        return self._fmt(obj.s3)

    @admin.display(description='Total Sah', ordering='total_sah_db')
    def total_suara_sah_fmt(self, obj):
        return self._fmt(obj.total_suara_sah)

    @admin.display(description='Tidak Sah', ordering='suara_tidak_sah')
    def suara_tidak_sah_fmt(self, obj):
        return self._fmt(obj.suara_tidak_sah)

    @admin.display(description='Total Masuk', ordering='total_masuk_db')
    def total_suara_masuk_fmt(self, obj):
        val = getattr(obj, 'total_masuk_db', obj.total_suara_masuk)
        return self._fmt(val)

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
        'nama', 'get_tps_total', 'get_dpt_total', 
        'suara_1_fmt', 'suara_2_fmt', 'suara_3_fmt',
        'total_suara_sah_fmt', 'suara_tidak_sah_fmt', 'total_suara_masuk_fmt'
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from django.db.models import Sum, OuterRef, Subquery, IntegerField
        from django.db.models.functions import Coalesce
        
        # Subquery untuk hitung total suara sah per kabupaten
        rekap_qs = RekapSuaraPilpres.objects.filter(kecamatan__kabupaten_kota=OuterRef('pk'))
        
        return qs.annotate(
            tps_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_tps'), 0),
            dpt_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_dpt'), 0),
            s1_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'),
                    paslon__no_urut=1
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(
                    total=Sum('jumlah_suara')
                ).values('total'),
                output_field=IntegerField()
            ), 0),
            s2_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'),
                    paslon__no_urut=2
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(
                    total=Sum('jumlah_suara')
                ).values('total'),
                output_field=IntegerField()
            ), 0),
            s3_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'),
                    paslon__no_urut=3
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(
                    total=Sum('jumlah_suara')
                ).values('total'),
                output_field=IntegerField()
            ), 0),
            sah_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk')
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(
                    total=Sum('jumlah_suara')
                ).values('total'),
                output_field=IntegerField()
            ), 0),
            tidak_sah_total=Coalesce(Subquery(
                rekap_qs.values('kecamatan__kabupaten_kota').annotate(
                    total=Sum('suara_tidak_sah')
                ).values('total'),
                output_field=IntegerField()
            ), 0)
        )

    def changelist_view(self, request, extra_context=None):
        """Update header kolom secara dinamis berdasarkan data Paslon terbaru."""
        from .models import PaslonPilpres
        paslons = {p.no_urut: p.foto_paslon.url for p in PaslonPilpres.objects.all() if p.foto_paslon}
        
        for no in range(1, 4):
            method_name = f'suara_{no}_fmt'
            method = getattr(self, method_name, None)
            if method and no in paslons:
                method.description = format_html(
                    '0{} <br> <img src="{}" style="width:25px;height:25px;border-radius:3px;border:1px solid #ddd;padding:1px;background:#fff;">', 
                    no, paslons[no]
                )
        return super().changelist_view(request, extra_context)

    def _fmt(self, val):
        return "{:,}".format(val or 0).replace(',', '.')

    @admin.display(description='TPS Total', ordering='tps_total')
    def get_tps_total(self, obj):
        return self._fmt(obj.tps_total)

    @admin.display(description='DPT Total', ordering='dpt_total')
    def get_dpt_total(self, obj):
        return self._fmt(obj.dpt_total)

    @admin.display(description='(01)', ordering='s1_total')
    def suara_1_fmt(self, obj):
        return self._fmt(obj.s1_total)

    @admin.display(description='(02)', ordering='s2_total')
    def suara_2_fmt(self, obj):
        return self._fmt(obj.s2_total)

    @admin.display(description='(03)', ordering='s3_total')
    def suara_3_fmt(self, obj):
        return self._fmt(obj.s3_total)

    @admin.display(description='Total Sah', ordering='sah_total')
    def total_suara_sah_fmt(self, obj):
        return self._fmt(obj.sah_total)

    @admin.display(description='Tidak Sah', ordering='tidak_sah_total')
    def suara_tidak_sah_fmt(self, obj):
        return self._fmt(obj.tidak_sah_total)

    @admin.display(description='Total Masuk')
    def total_suara_masuk_fmt(self, obj):
        return self._fmt(obj.sah_total + obj.tidak_sah_total)
