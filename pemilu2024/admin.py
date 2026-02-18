from django.contrib import admin
from django.db.models import Sum, Count, Q
from django.utils.html import format_html
from django import forms
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from import_export.formats.base_formats import XLSX
from .models import (
    Partai, PaslonPilpres, PaslonPilkada, KabupatenKota, Kecamatan, KelurahanDesa, 
    DapilRI, DapilProvinsi, DapilKabKota, CalegRI, CalegProvinsi, CalegKabKota, 
    SuaraPilpres, RekapTPSDPT, RekapTPSDPTKecamatan, SuaraPilpresKecamatan,
    GeoKokab, GeoKecamatan, GeoDesKel
)
from functools import lru_cache

# =========================================================================
# BAGIAN 0: UTILITIES, MIXINS & CACHE
# =========================================================================

@lru_cache(maxsize=1)
def get_cached_paslon_names():
    """Cache nama paslon agar tidak query database terus menerus di List View"""
    paslons = PaslonPilpres.objects.all().order_by('no_urut')
    return {p.no_urut: p.nama_capres for p in paslons}

def clear_paslon_cache():
    get_cached_paslon_names.cache_clear()

class PaslonAdminMixin:
    """Mixin untuk fungsi display yang sama antara Pilpres & Pilkada"""
    
    def get_image_preview(self, image_field):
        """Helper untuk preview foto paslon/logo partai"""
        if image_field:
            return f'<img src="{image_field.url}" width="50" height="50" style="object-fit: contain;" />'
        return '<div style="width: 50px; height: 50px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; color: #999; font-size: 9px;">No Image</div>'

    def koalisi_partai(self, obj):
        """Display logo-logo partai pengusul"""
        partai_list = obj.koalisi.all()
        if not partai_list:
            return "-"
        
        logos_html = []
        for partai in partai_list:
            if partai.logo:
                logo_img = f'<img src="{partai.logo.url}" width="30" height="30" style="object-fit: contain; margin-right: 5px; vertical-align: middle;" title="{partai.nama_partai}" />'
            else:
                logo_img = f'<div style="display: inline-block; width: 30px; height: 30px; background: #f0f0f0; margin-right: 5px; vertical-align: middle; text-align: center; line-height: 30px; font-size: 8px; color: #999;" title="{partai.nama_partai}">?</div>'
            logos_html.append(logo_img)
        
        return format_html(''.join(logos_html))
    koalisi_partai.short_description = "Gabungan Parpol Pengusul"


# =========================================================================
# BAGIAN 1: MASTER DATA WILAYAH (UTAMA)
# =========================================================================

# --- 1.1 KABUPATEN/KOTA ---
class KabupatenKotaResource(resources.ModelResource):
    class Meta:
        model = KabupatenKota
        fields = ('nama',)
        export_order = ('nama',)
        import_id_fields = ['nama']
        skip_unchanged = True

    def get_import_display(self, row):
        return row.get('nama')

class GeoKokabInline(admin.StackedInline):
    model = GeoKokab
    verbose_name = "Data Peta Batas Wilayah (GeoJSON)"
    verbose_name_plural = "Data Peta Batas Wilayah (GeoJSON)"
    readonly_fields = ['preview_peta']
    extra = 0
    max_num = 1

    def preview_peta(self, obj):
        return GeoKokabAdmin.preview_peta(self, obj)
    preview_peta.short_description = "Preview Peta"

@admin.register(KabupatenKota)
class KabupatenKotaAdmin(ImportExportModelAdmin, PaslonAdminMixin):
    resource_class = KabupatenKotaResource
    inlines = [GeoKokabInline]
    list_display = ['nama', 'rekap_tps_dpt', 'rekap_pilpres', 'lihat_kecamatan']
    search_fields = ['nama']
    ordering = ['nama']
    readonly_fields = ['nama']
    list_per_page = 10
    formats = [XLSX]

    def has_delete_permission(self, request, obj=None):
        return False

    def lihat_kecamatan(self, obj):
        """Link untuk melihat daftar kecamatan di kabupaten ini"""
        from django.urls import reverse
        url = reverse('admin:pemilu2024_kecamatan_changelist')
        return format_html(
            '<a class="button" href="{}?kabupaten_kota__id__exact={}" style="background: #17a2b8; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; text-decoration: none; font-weight: bold; white-space: nowrap;">'
            '<i class="fas fa-eye" style="margin-right: 5px;"></i>Detail Kecamatan'
            '</a>',
            url, obj.id
        )
    lihat_kecamatan.short_description = "Aksi"

    def get_progress_bar(self, current, total, label="DATA"):
        """Helper untuk membuat HTML Progress Bar minimalis"""
        if total <= 0: return ""
        percent = min((current / total) * 100, 100)
        color = "#28a745" if percent == 100 else "#ffc107" if percent >= 50 else "#17a2b8"
        return format_html(
            '<div style="width: 100%; max-width: 250px; margin-top: 5px;">'
            '<div style="font-size: 7px; color: #666; margin-bottom: 1px; font-weight: bold;">PROGRES {}: {}/{} KEC ({}%)</div>'
            '<div style="width: 100%; height: 4px; background: #eee; border-radius: 2px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: {}; transition: width 0.3s;"></div>'
            '</div>'
            '</div>',
            label.upper(), current, total, f"{percent:.0f}", f"{percent:.0f}", color
        )

    def rekap_tps_dpt(self, obj):
        """Dashboard TPS & DPT tingkat Kabupaten (Agregasi Kecamatan)"""
        tps = obj.tps_pemilu_sum or 0
        dpt = obj.dpt_pemilu_sum or 0
        
        # Grafik Progress (Gabungan/TPS saja sesuai request)
        progress_tps = self.get_progress_bar(obj.filled_tps_count, obj.total_kec_count, "TPS/DPT")
        
        # Format numbers
        tps_fmt = f"{tps:,}"
        dpt_fmt = f"{dpt:,}"

        return format_html(
            '<div style="min-width: 160px; padding: 2px 0;">'
            '<div style="display: flex; gap: 5px; margin-bottom: 5px; white-space: nowrap;">'
            '<span style="background: #17a2b8; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;">TPS: {}</span>'
            '<span style="background: #6c757d; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;">DPT: {}</span>'
            '</div>'
            '<div style="margin-top: 2px;">{}</div>'
            '</div>', 
            tps_fmt, dpt_fmt, progress_tps
        )
    rekap_tps_dpt.short_description = "Data TPS/DPT Kabupaten"

    def rekap_pilpres(self, obj):
        """Dashboard Pilpres tingkat Kabupaten (Agregasi Kecamatan)"""
        # Grafik Progress
        progress_entry = self.get_progress_bar(obj.filled_pilpres_count, obj.total_kec_count, "ENTRY")

        s1 = obj.p1_sum or 0
        s2 = obj.p2_sum or 0
        s3 = obj.p3_sum or 0
        st = obj.tidak_sah_sum or 0
        
        total_sah = s1 + s2 + s3
        total_masuk = total_sah + st
        
        if total_masuk == 0:
            return format_html(
                '<div style="min-width: 200px; padding: 2px 0;">'
                '<div style="color: #999; font-size: 11px; margin-bottom: 5px;">Belum ada data</div>'
                '<div style="margin-top: 2px;">{}</div>'
                '</div>',
                progress_entry
            )

        # Hitung Persentase
        p1_pct = (s1 / total_sah * 100) if total_sah > 0 else 0
        p2_pct = (s2 / total_sah * 100) if total_sah > 0 else 0
        p3_pct = (s3 / total_sah * 100) if total_sah > 0 else 0

        def get_badge(no, suara, persen, color):
            # Pre-format number
            suara_fmt = f"{suara:,}"
            return format_html(
                '<div style="display: flex; align-items: center; gap: 5px; margin-bottom: 2px; white-space: nowrap;">'
                '<span style="background: {}; color: white; min-width: 14px; height: 14px; display: inline-flex; align-items: center; justify-content: center; border-radius: 3px; font-size: 8px; font-weight: bold;">{}</span>'
                '<span style="font-weight: bold; color: #333; font-size: 11px;">{}</span>'
                '<small style="color: #666; font-size: 9px;">({:.0f}%)</small>'
                '</div>',
                color, no, suara_fmt, persen
            )

        rows = format_html('<div style="flex: 1;">{}{}{}</div>', 
                           get_badge("1", s1, p1_pct, "#fd7e14"),
                           get_badge("2", s2, p2_pct, "#007bff"),
                           get_badge("3", s3, p3_pct, "#dc3545"))

        # Pre-format stats
        sah_fmt = f"{total_sah:,}"
        st_fmt = f"{st:,}"
        total_fmt = f"{total_masuk:,}"

        stats = format_html(
            '<div style="border-left: 1px solid #ddd; padding-left: 10px; margin-left: 10px; display: flex; flex-direction: column; justify-content: center; gap: 3px;">'
            '<div style="font-size: 10px; color: #333; white-space: nowrap;">SAH: <strong>{}</strong></div>'
            '<div style="font-size: 10px; color: #666; white-space: nowrap;">T.SAH: {}</div>'
            '<div style="font-size: 10px; color: #000; white-space: nowrap; border-top: 1px solid #eee; padding-top: 2px;">TOTAL: <strong>{}</strong></div>'
            '</div>',
            sah_fmt, st_fmt, total_fmt
        )

        return format_html(
            '<div style="min-width: 200px; padding: 2px 0;">'
            '<div style="display: flex; align-items: stretch; margin-bottom: 5px;">{} {}</div>'
            '<div style="margin-top: 2px;">{}</div>'
            '</div>', 
            rows, stats, progress_entry
        )
    rekap_pilpres.short_description = "Data Pilpres Kabupaten"

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_kec_count=Count('kecamatan_set', distinct=True),
            filled_tps_count=Count('kecamatan_set__rekap_tps_dpt_kecamatan', filter=Q(kecamatan_set__rekap_tps_dpt_kecamatan__tps_pemilu__gt=0), distinct=True),
            filled_dpt_count=Count('kecamatan_set__rekap_tps_dpt_kecamatan', filter=Q(kecamatan_set__rekap_tps_dpt_kecamatan__dpt_pemilu__gt=0), distinct=True),
            filled_pilpres_count=Count('kecamatan_set__rekap_suara_pilpres_kecamatan', distinct=True),
            tps_pemilu_sum=Sum('kecamatan_set__rekap_tps_dpt_kecamatan__tps_pemilu'),
            dpt_pemilu_sum=Sum('kecamatan_set__rekap_tps_dpt_kecamatan__dpt_pemilu'),
            p1_sum=Sum('kecamatan_set__rekap_suara_pilpres_kecamatan__suara_paslon_1'),
            p2_sum=Sum('kecamatan_set__rekap_suara_pilpres_kecamatan__suara_paslon_2'),
            p3_sum=Sum('kecamatan_set__rekap_suara_pilpres_kecamatan__suara_paslon_3'),
            tidak_sah_sum=Sum('kecamatan_set__rekap_suara_pilpres_kecamatan__suara_tidak_sah'),
        )

# --- 1.2 KECAMATAN ---
class KecamatanResource(resources.ModelResource):
    kabupaten_kota = fields.Field(
        column_name='kabupaten_kota',
        attribute='kabupaten_kota',
        widget=widgets.ForeignKeyWidget(KabupatenKota, 'nama')
    )

    class Meta:
        model = Kecamatan
        fields = ('kabupaten_kota', 'nama')
        export_order = ('kabupaten_kota', 'nama')
        import_id_fields = ['kabupaten_kota', 'nama']
        skip_unchanged = True

    def get_import_display(self, row):
        return f"{row.get('nama')} -> {row.get('kabupaten_kota')}"

class SuaraPilpresKecamatanAdminForm(forms.ModelForm):
    class Meta:
        model = SuaraPilpresKecamatan
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Label Dinamis dari Cache
        names = get_cached_paslon_names()
        for i in range(1, 4):
            field_name = f'suara_paslon_{i}'
            if field_name in self.fields:
                self.fields[field_name].label = f"{i:02d} - {names.get(i, f'Paslon {i}')}"
    
    class Media:
        js = (
            'admin/js/suara_pilpres_calculator.js',
        )

class GeoKecamatanInline(admin.StackedInline):
    model = GeoKecamatan
    verbose_name = "Data Peta Batas Wilayah (GeoJSON)"
    verbose_name_plural = "Data Peta Batas Wilayah (GeoJSON)"
    readonly_fields = ['preview_peta']
    extra = 0
    max_num = 1

    def preview_peta(self, obj):
        return GeoKokabAdmin.preview_peta(self, obj)
    preview_peta.short_description = "Preview Peta"

class RekapTPSDPTKecamatanInline(admin.StackedInline):
    model = RekapTPSDPTKecamatan
    can_delete = False
    verbose_name = "Rekap TPS & DPT Kecamatan"
    verbose_name_plural = "Data TPS & DPT Kecamatan"
    max_num = 1

class SuaraPilpresKecamatanInline(admin.StackedInline):
    model = SuaraPilpresKecamatan
    form = SuaraPilpresKecamatanAdminForm
    can_delete = False
    verbose_name = "Rekap Suara Pilpres Kecamatan"
    verbose_name_plural = "Data Suara Pilpres Kecamatan"
    max_num = 1

    def total_suara_sah_display(self, obj):
        if obj and obj.pk: return f"{obj.total_suara_sah:,}"
        return 0
    total_suara_sah_display.short_description = "Total Suara Sah"

    def total_suara_masuk_display(self, obj):
        if obj and obj.pk: return f"{obj.total_suara_masuk:,}"
        return 0
    total_suara_masuk_display.short_description = "Total Suara Masuk"

    fieldsets = (
        ('Data Perolehan Suara (Kecamatan)', {
            'fields': ('suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah')
        }),
        ('Monitoring (Otomatis)', {
            'fields': ('total_suara_sah_display', 'total_suara_masuk_display'),
            'description': '<div style="color: #d9534f; font-weight: bold; margin-top: -10px;">Angka di bawah ini akan terupdate otomatis saat Anda mengetik.</div>'
        }),
    )
    readonly_fields = ['total_suara_sah_display', 'total_suara_masuk_display']

@admin.register(Kecamatan)
class KecamatanAdmin(ImportExportModelAdmin, PaslonAdminMixin):
    inlines = [RekapTPSDPTKecamatanInline, SuaraPilpresKecamatanInline, GeoKecamatanInline]
    
    list_display = ['info_kecamatan', 'rekap_tps_dpt', 'rekap_pilpres', 'progress_data_desa', 'lihat_desa']
    list_per_page = 10
    list_display_links = ['info_kecamatan']
    list_filter = ['kabupaten_kota']

    search_fields = ['nama', 'kabupaten_kota__nama']
    ordering = ['kabupaten_kota', 'nama']
    formats = [XLSX]

    def lihat_desa(self, obj):
        """Link untuk melihat daftar desa yang difilter berdasarkan kecamatan ini"""
        from django.urls import reverse
        url = reverse('admin:pemilu2024_kelurahandesa_changelist')
        return format_html(
            '<a class="button" href="{}?kecamatan__id__exact={}" style="background: #17a2b8; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; text-decoration: none; font-weight: bold; white-space: nowrap;">'
            '<i class="fas fa-eye" style="margin-right: 5px;"></i>Detail Desa'
            '</a>',
            url, obj.id
        )
    lihat_desa.short_description = "Aksi"

    def info_kecamatan(self, obj):
        """Menampilkan Nama Kecamatan dan Kabupaten dalam satu kolom"""
        return format_html(
            '<div style="line-height: 1.4;">'
            '<strong style="font-size: 14px; color: #333;">{}</strong><br>'
            '<small style="color: #666;">{}</small>'
            '</div>',
            obj.nama.upper(),
            obj.kabupaten_kota.nama
        )
    info_kecamatan.short_description = "Wilayah Kecamatan"
    info_kecamatan.admin_order_field = 'nama'

    def get_progress_bar(self, current, total, label="DATA"):
        """Helper untuk membuat HTML Progress Bar minimalis"""
        if total <= 0: return ""
        percent = min((current / total) * 100, 100)
        color = "#28a745" if percent == 100 else "#ffc107" if percent >= 50 else "#17a2b8"
        return format_html(
            '<div style="width: 100%; max-width: 250px; margin-top: 5px;">'
            '<div style="font-size: 7px; color: #666; margin-bottom: 1px; font-weight: bold;">PROGRES {}: {}/{} DESA ({}%)</div>'
            '<div style="width: 100%; height: 4px; background: #eee; border-radius: 2px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: {}; transition: width 0.3s;"></div>'
            '</div>'
            '</div>',
            label.upper(), current, total, f"{percent:.0f}", f"{percent:.0f}", color
        )

    def rekap_tps_dpt(self, obj):
        """Dashboard TPS & DPT tingkat Kecamatan"""
        # Data Tingkat Kecamatan
        has_data = hasattr(obj, 'rekap_tps_dpt_kecamatan')
        tps = obj.rekap_tps_dpt_kecamatan.tps_pemilu if has_data else 0
        dpt = obj.rekap_tps_dpt_kecamatan.dpt_pemilu if has_data else 0

        progress_tps = self.get_progress_bar(obj.filled_tps_count, obj.total_desa_count, "TPS")
        progress_dpt = self.get_progress_bar(obj.filled_dpt_count, obj.total_desa_count, "DPT")

        if not has_data:
            return format_html('<div style="min-width: 140px; color: #999; font-size: 11px;">Belum diinput</div>')

        # Force convert to int to prevent string formatting errors
        try:
            tps_int = int(tps)
            dpt_int = int(dpt)
        except (ValueError, TypeError):
            tps_int, dpt_int = 0, 0

        # Format numbers first
        tps_fmt = f"{tps_int:,}"
        dpt_fmt = f"{dpt_int:,}"

        return format_html(
            '<div style="min-width: 160px; padding: 2px 0;">'
            '<div style="display: flex; gap: 5px; margin-bottom: 2px; white-space: nowrap;">'
            '<span style="background: #17a2b8; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;">TPS: {}</span>'
            '<span style="background: #6c757d; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;">DPT: {}</span>'
            '</div>'
            '</div>', 
            tps_fmt, dpt_fmt
        )
    rekap_tps_dpt.short_description = "Data TPS/DPT Kecamatan"

    def progress_data_desa(self, obj):
        """Kolom Terpisah: Menggabungkan semua progres data dari tingkat desa"""
        p_tps = self.get_progress_bar(obj.filled_tps_count, obj.total_desa_count, "TPS")
        p_dpt = self.get_progress_bar(obj.filled_dpt_count, obj.total_desa_count, "DPT")
        p_entry = self.get_progress_bar(obj.filled_pilpres_count, obj.total_desa_count, "ENTRY")
        
        return format_html(
            '<div style="min-width: 180px; padding: 2px 0;">'
            '{} {} {}'
            '</div>',
            p_tps, p_dpt, p_entry
        )
    progress_data_desa.short_description = "Progress Data Desa"

    def rekap_pilpres(self, obj):
        """Dashboard Pilpres tingkat Kecamatan"""
        # Data Tingkat Kecamatan
        has_data = hasattr(obj, 'rekap_suara_pilpres_kecamatan')
        resmi = obj.rekap_suara_pilpres_kecamatan if has_data else None
        
        if not resmi:
            return format_html('<div style="min-width: 200px; color: #999; font-size: 11px;">Belum diinput</div>')

        # Force convert all values to int
        try:
            s1 = int(resmi.suara_paslon_1 or 0)
            s2 = int(resmi.suara_paslon_2 or 0)
            s3 = int(resmi.suara_paslon_3 or 0)
            st = int(resmi.suara_tidak_sah or 0)
        except (ValueError, TypeError):
            s1, s2, s3, st = 0, 0, 0, 0
            
        total_sah = int(s1 + s2 + s3)
        total_masuk = int(total_sah + st)
        
        # Hitung Persentase
        p1_pct = (s1 / total_sah * 100) if total_sah > 0 else 0
        p2_pct = (s2 / total_sah * 100) if total_sah > 0 else 0
        p3_pct = (s3 / total_sah * 100) if total_sah > 0 else 0

        def get_badge(no, suara, persen, color):
            # Pre-format number
            suara_fmt = f"{suara:,}"
            return format_html(
                '<div style="display: flex; align-items: center; gap: 5px; margin-bottom: 2px; white-space: nowrap;">'
                '<span style="background: {}; color: white; min-width: 14px; height: 14px; display: inline-flex; align-items: center; justify-content: center; border-radius: 3px; font-size: 8px; font-weight: bold;">{}</span>'
                '<span style="font-weight: bold; color: #333; font-size: 11px;">{}</span>'
                '<small style="color: #666; font-size: 9px;">({:.0f}%)</small>'
                '</div>',
                color, no, suara_fmt, persen
            )

        rows = format_html('<div style="flex: 1;">{}{}{}</div>', 
                           get_badge("1", s1, p1_pct, "#fd7e14"),
                           get_badge("2", s2, p2_pct, "#007bff"),
                           get_badge("3", s3, p3_pct, "#dc3545"))

        # Pre-format stats
        sah_fmt = f"{total_sah:,}"
        st_fmt = f"{st:,}"
        total_fmt = f"{total_masuk:,}"

        stats = format_html(
            '<div style="border-left: 1px solid #ddd; padding-left: 10px; margin-left: 10px; display: flex; flex-direction: column; justify-content: center; gap: 3px;">'
            '<div style="font-size: 10px; color: #333; white-space: nowrap;">SAH: <strong>{}</strong></div>'
            '<div style="font-size: 10px; color: #666; white-space: nowrap;">T.SAH: {}</div>'
            '<div style="font-size: 10px; color: #000; white-space: nowrap; border-top: 1px solid #eee; padding-top: 2px;">TOTAL: <strong>{}</strong></div>'
            '</div>',
            sah_fmt, st_fmt, total_fmt
        )

        return format_html(
            '<div style="min-width: 200px; padding: 2px 0;">'
            '<div style="display: flex; align-items: stretch;">{} {}</div>'
            '</div>', 
            rows, stats
        )
    rekap_pilpres.short_description = "Data Pilpres Kecamatan"

    def has_delete_permission(self, request, obj=None):
        """Mencegah penghapusan data Kecamatan agar rekapitulasi tetap aman"""
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('kabupaten_kota').prefetch_related(
            'rekap_tps_dpt_kecamatan', 
            'rekap_suara_pilpres_kecamatan'
        ).annotate(
            total_desa_count=Count('kelurahandesa', distinct=True),
            filled_tps_count=Count('kelurahandesa__rekap_tps_dpt', filter=Q(kelurahandesa__rekap_tps_dpt__tps_pemilu__gt=0), distinct=True),
            filled_dpt_count=Count('kelurahandesa__rekap_tps_dpt', filter=Q(kelurahandesa__rekap_tps_dpt__dpt_pemilu__gt=0), distinct=True),
            filled_pilpres_count=Count('kelurahandesa__rekap_suara_pilpres', distinct=True),
            tps_pemilu_sum=Sum('kelurahandesa__rekap_tps_dpt__tps_pemilu'),
            dpt_pemilu_sum=Sum('kelurahandesa__rekap_tps_dpt__dpt_pemilu'),
            p1_sum=Sum('kelurahandesa__rekap_suara_pilpres__suara_paslon_1'),
            p2_sum=Sum('kelurahandesa__rekap_suara_pilpres__suara_paslon_2'),
            p3_sum=Sum('kelurahandesa__rekap_suara_pilpres__suara_paslon_3'),
            tidak_sah_sum=Sum('kelurahandesa__rekap_suara_pilpres__suara_tidak_sah'),
        )

# --- 1.3 KELURAHAN/DESA DEPENDENCIES (FORMS & INLINES) ---
class SmartKecamatanWidget(widgets.ForeignKeyWidget):
    """Widget khusus untuk mencari Kecamatan berdasarkan Nama DAN Kabupaten-nya"""
    def clean(self, value, row=None, **kwargs):
        kab_name = row.get('kabupaten') or row.get('kabupaten_kota')
        if value and kab_name:
            return self.model.objects.get(
                nama=value,
                kabupaten_kota__nama=kab_name
            )
        return super().clean(value, row, **kwargs)

class SuaraPilpresAdminForm(forms.ModelForm):
    kabupaten = forms.ModelChoiceField(queryset=KabupatenKota.objects.all().order_by('nama'), required=False, label="Kabupaten/Kota")
    kecamatan = forms.ModelChoiceField(queryset=Kecamatan.objects.none(), required=False, label="Kecamatan")

    class Meta:
        model = SuaraPilpres
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.desa:
            self.fields['kabupaten'].initial = self.instance.desa.kabupaten
            self.fields['kecamatan'].initial = self.instance.desa.kecamatan
            self.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten_kota=self.instance.desa.kabupaten).order_by('nama')
            if 'desa' in self.fields:
                self.fields['desa'].queryset = KelurahanDesa.objects.filter(kecamatan=self.instance.desa.kecamatan).order_by('desa_kelurahan')
        elif self.data and 'kabupaten' in self.data:
            try:
                kab_id = int(self.data.get('kabupaten'))
                self.fields['kecamatan'].queryset = Kecamatan.objects.filter(kabupaten_kota_id=kab_id).order_by('nama')
            except (ValueError, TypeError): pass
            
            if 'kecamatan' in self.data:
                try:
                    kec_id = int(self.data.get('kecamatan'))
                    if 'desa' in self.fields:
                        self.fields['desa'].queryset = KelurahanDesa.objects.filter(kecamatan_id=kec_id).order_by('desa_kelurahan')
                except (ValueError, TypeError): pass

        # Label Dinamis dari Cache
        names = get_cached_paslon_names()
        for i in range(1, 4):
            field_name = f'suara_paslon_{i}'
            if field_name in self.fields:
                self.fields[field_name].label = f"{i:02d} - {names.get(i, f'Paslon {i}')}"

    class Media:
        js = (
            'admin/js/region_ajax_selector.js',
            'admin/js/suara_pilpres_calculator.js',
        )

class RekapTPSDPTInline(admin.StackedInline):
    model = RekapTPSDPT
    can_delete = False
    verbose_name = "TPS & DPT"
    verbose_name_plural = "Data TPS & DPT"
    fieldsets = (
        ('Data Pemilu 2024', {
            'fields': ('tps_pemilu', 'dpt_pemilu')
        }),
    )
    max_num = 1

class SuaraPilpresInline(admin.StackedInline):
    model = SuaraPilpres
    form = SuaraPilpresAdminForm
    can_delete = False
    verbose_name = "Suara Pilpres"
    verbose_name_plural = "Perolehan Suara Pilpres"
    
    def total_suara_sah_display(self, obj):
        if obj and obj.pk:
            return f"{obj.total_suara_sah:,}"
        return 0
    total_suara_sah_display.short_description = "Total Suara Sah"

    def total_suara_masuk_display(self, obj):
        if obj and obj.pk:
            return f"{obj.total_suara_masuk:,}"
        return 0
    total_suara_masuk_display.short_description = "Total Suara Masuk"

    fieldsets = (
        ('Data Perolehan Suara', {
            'fields': ('suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah')
        }),
        ('Monitoring (Otomatis)', {
            'fields': ('total_suara_sah_display', 'total_suara_masuk_display'),
            'description': '<div style="color: #d9534f; font-weight: bold; margin-top: -10px;">Angka di bawah ini akan terupdate otomatis saat Anda mengetik.</div>'
        }),
    )
    readonly_fields = ['total_suara_sah_display', 'total_suara_masuk_display']
    max_num = 1

# --- 1.4 KELURAHAN/DESA ---
class KelurahanDesaResource(resources.ModelResource):
    kabupaten = fields.Field(column_name='kabupaten', attribute='kabupaten', widget=widgets.ForeignKeyWidget(KabupatenKota, 'nama'))
    kecamatan = fields.Field(column_name='kecamatan', attribute='kecamatan', widget=SmartKecamatanWidget(Kecamatan, 'nama'))

    class Meta:
        model = KelurahanDesa
        fields = ('kabupaten', 'kecamatan', 'desa_kelurahan')
        export_order = ('kabupaten', 'kecamatan', 'desa_kelurahan')
        import_id_fields = ['kabupaten', 'kecamatan', 'desa_kelurahan']
        skip_unchanged = True

    def before_import(self, dataset, **kwargs):
        mapping = {'kabupaten_kota': 'kabupaten', 'nama': 'desa_kelurahan'}
        new_headers = []
        for header in dataset.headers:
            lowered_header = str(header).lower().strip()
            found = False
            for alt, official in mapping.items():
                if lowered_header == alt:
                    new_headers.append(official)
                    found = True
                    break
            if not found:
                new_headers.append(header)
        dataset.headers = new_headers

    def get_import_display(self, row):
        return f"{row.get('desa_kelurahan')} -> {row.get('kecamatan')} ({row.get('kabupaten')})"

class GeoDesKelInline(admin.StackedInline):
    model = GeoDesKel
    verbose_name = "Data Peta Batas Wilayah (GeoJSON)"
    verbose_name_plural = "Data Peta Batas Wilayah (GeoJSON)"
    readonly_fields = ['preview_peta']
    extra = 0
    max_num = 1

    def preview_peta(self, obj):
        return GeoKokabAdmin.preview_peta(self, obj)
    preview_peta.short_description = "Preview Peta"

@admin.register(KelurahanDesa)
class KelurahanDesaAdmin(ImportExportModelAdmin, PaslonAdminMixin):
    resource_class = KelurahanDesaResource
    inlines = [RekapTPSDPTInline, SuaraPilpresInline, GeoDesKelInline]
    list_display = ['info_desa', 'status_tps_dpt', 'status_pilpres']
    list_display_links = ['info_desa']
    list_filter = ['kabupaten', 'kecamatan']
    search_fields = ['desa_kelurahan', 'kecamatan__nama', 'kabupaten__nama']
    ordering = ['kabupaten', 'kecamatan', 'desa_kelurahan']
    formats = [XLSX]

    def info_desa(self, obj):
        """Menampilkan Nama Desa, Kecamatan, dan Kabupaten"""
        return format_html(
            '<div style="line-height: 1.4;">'
            '<strong style="font-size: 14px; color: #333;">{}</strong><br>'
            '<small style="color: #666;">Kec. {} | {}</small>'
            '</div>',
            obj.desa_kelurahan.upper(),
            obj.kecamatan.nama,
            obj.kabupaten.nama
        )
    info_desa.short_description = "Wilayah Desa/Kelurahan"
    info_desa.admin_order_field = 'desa_kelurahan'

    def status_tps_dpt(self, obj):
        """Tampilan Dashboard Mini TPS & DPT Desa (Samain format dengan Kecamatan)"""
        if not hasattr(obj, 'rekap_tps_dpt'):
            return format_html('<div style="display: flex; justify-content: center; min-width: 140px;"><img src="/static/admin/img/icon-no.svg" alt="False"></div>')
        
        rekap = obj.rekap_tps_dpt
        
        return format_html(
            '<div style="min-width: 160px; padding: 2px 0;">'
            '<div style="display: flex; gap: 5px; white-space: nowrap;">'
            '<span style="background: #17a2b8; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;">TPS: {}</span>'
            '<span style="background: #6c757d; color: white; padding: 2px 5px; border-radius: 3px; font-size: 10px; font-weight: bold;">DPT: {}</span>'
            '</div>'
            '</div>',
            rekap.tps_pemilu, f"{rekap.dpt_pemilu:,}"
        )
    status_tps_dpt.short_description = "Data TPS/DPT"

    def status_pilpres(self, obj):
        """Tampilan Dashboard Mini Hasil Pilpres Desa dengan Ringkasan Sah/T.Sah"""
        if not hasattr(obj, 'rekap_suara_pilpres'):
            return format_html('<div style="display: flex; justify-content: center; min-width: 130px;"><img src="/static/admin/img/icon-no.svg" alt="False"></div>')
        
        rekap = obj.rekap_suara_pilpres
        total_sah = rekap.total_suara_sah
        tidak_sah = rekap.suara_tidak_sah or 0
        total_masuk = total_sah + tidak_sah
        
        # Ambil DPT dari relasi rekap_tps_dpt
        dpt_desa = obj.rekap_tps_dpt.dpt_pemilu if hasattr(obj, 'rekap_tps_dpt') else 0
        
        if total_sah <= 0 and tidak_sah <= 0:
            return format_html('<div style="text-align: center; color: #28a745; font-weight: bold; min-width: 130px;">(Terisi)</div>')

        # Hitung Persentase Paslon
        p1_pct = (rekap.suara_paslon_1 / total_sah * 100) if total_sah > 0 else 0
        p2_pct = (rekap.suara_paslon_2 / total_sah * 100) if total_sah > 0 else 0
        p3_pct = (rekap.suara_paslon_3 / total_sah * 100) if total_sah > 0 else 0

        # Hitung Persentase Statistik
        sah_pct = f"{(total_sah / total_masuk * 100):.0f}" if total_masuk > 0 else "0"
        tsah_pct = f"{(tidak_sah / total_masuk * 100):.0f}" if total_masuk > 0 else "0"
        partisipasi_pct = f"{(total_masuk / dpt_desa * 100):.1f}" if dpt_desa > 0 else "0.0"

        def get_badge_html(no, suara, persen, color):
            persen_str = f"{persen:.0f}"
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px; white-space: nowrap;">'
                '<span style="background: {}; color: white; min-width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; border-radius: 4px; font-size: 10px; font-weight: bold;">{}</span>'
                '<span style="font-weight: bold; color: #333; font-size: 12px;">{}</span>'
                '<small style="color: #666; font-size: 10px;">({}%)</small>'
                '</div>',
                color, no, f"{suara:,}", persen_str
            )

        row1 = get_badge_html("1", rekap.suara_paslon_1, p1_pct, "#fd7e14")
        row2 = get_badge_html("2", rekap.suara_paslon_2, p2_pct, "#007bff")
        row3 = get_badge_html("3", rekap.suara_paslon_3, p3_pct, "#dc3545")

        totals_html = format_html(
            '<div style="border-left: 1px solid #ddd; padding-left: 10px; margin-left: 10px; display: flex; flex-direction: column; justify-content: center; gap: 4px;">'
            '<div style="display: flex; align-items: center; gap: 5px; white-space: nowrap;"><span style="background: #28a745; color: white; min-width: 38px; height: 14px; display: inline-flex; align-items: center; justify-content: center; border-radius: 3px; font-size: 8px; font-weight: bold;">SAH</span> <strong style="font-size: 11px; color: #333;">{}</strong> <small style="color: #666; font-size: 9px;">({}%)</small></div>'
            '<div style="display: flex; align-items: center; gap: 5px; white-space: nowrap;"><span style="background: #dc3545; color: white; min-width: 38px; height: 14px; display: inline-flex; align-items: center; justify-content: center; border-radius: 3px; font-size: 8px; font-weight: bold;">T.SAH</span> <strong style="font-size: 11px; color: #333;">{}</strong> <small style="color: #666; font-size: 9px;">({}%)</small></div>'
            '<div style="display: flex; align-items: center; gap: 5px; white-space: nowrap;"><span style="background: #6c757d; color: white; min-width: 38px; height: 14px; display: inline-flex; align-items: center; justify-content: center; border-radius: 3px; font-size: 8px; font-weight: bold;">TOTAL</span> <strong style="font-size: 11px; color: #333;">{}</strong> <small style="color: #007bff; font-size: 9px; font-weight: bold;">({}%)</small></div>'
            '</div>',
            f"{total_sah:,}", sah_pct, f"{tidak_sah:,}", tsah_pct, f"{total_masuk:,}", partisipasi_pct
        )

        return format_html(
            '<div style="min-width: 250px; padding: 2px 0; display: flex; align-items: stretch;">'
            '<div style="flex: 1;">{}{}{}</div>'
            '{}'
            '</div>', 
            row1, row2, row3, totals_html
        )
    status_pilpres.short_description = "Hasil Pilpres"

    def has_delete_permission(self, request, obj=None):
        """Mencegah penghapusan data Desa/Kelurahan agar rekap suara tetap aman"""
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('kecamatan', 'kabupaten').prefetch_related('rekap_tps_dpt', 'rekap_suara_pilpres')


# =========================================================================
# BAGIAN 2: PARTAI & STRUKTUR PENCALEGAN (KPU)
# =========================================================================

# --- 2.1 PARTAI ---
class PartaiResource(resources.ModelResource):
    class Meta:
        model = Partai
        fields = ('no_urut', 'nama_partai', 'logo')
        export_order = ('no_urut', 'nama_partai', 'logo')
        import_id_fields = ['no_urut']
        skip_unchanged = True
        report_skipped = True

@admin.register(Partai)
class PartaiAdmin(admin.ModelAdmin, PaslonAdminMixin): # GANTI INI (ImportExportModelAdmin -> admin.ModelAdmin)
    #resource_class = PartaiResource
    list_display = ['info_lengkap']
    # list_display_links = ['info_lengkap']
    list_display_links = None
    ordering = ['no_urut']
    search_fields = ['nama_partai', 'no_urut']
    list_filter = ['nama_partai', 'no_urut']
    #formats = [XLSX]

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # PENGATURAN IZIN (Ubah ke True kalau mau Edit/Tambah/Hapus lagi)
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def has_add_permission(self, request):
        """Mencegah Tambah Data Partai Baru"""
        return False

    def has_change_permission(self, request, obj=None):
        """Mencegah Edit Data Partai"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Mencegah Hapus Data Partai"""
        return False
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    
    def info_lengkap(self, obj):
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<div>{}</div>'
            '<div>'
            '<strong style="font-size: 14px;">{}</strong><br>'
            '<small style="color: #666;">No. Urut: {}</small>'
            '</div>'
            '</div>',
            format_html(self.get_image_preview(obj.logo)),
            obj.nama_partai,
            obj.no_urut
        )
    info_lengkap.short_description = "Data Partai"

# --- 2.2 DAPIL RI ---
class DapilRIAdminForm(forms.ModelForm):
    class Meta:
        model = DapilRI
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        used_ids = DapilRI.objects.exclude(pk=self.instance.pk if self.instance.pk else None).values_list('wilayah', flat=True)
        self.fields['wilayah'].queryset = KabupatenKota.objects.exclude(id__in=used_ids).order_by('nama')
    def clean_wilayah(self):
        wilayah = self.cleaned_data.get('wilayah')
        for kab in wilayah:
            query = DapilRI.objects.filter(wilayah=kab)
            if self.instance.pk: query = query.exclude(pk=self.instance.pk)
            if query.exists(): raise forms.ValidationError(f"{kab.nama} sudah masuk di Dapil RI {query.first().nama}")
        return wilayah

@admin.register(DapilRI)
class DapilRIAdmin(admin.ModelAdmin):
    form = DapilRIAdminForm
    list_display = ['nama', 'alokasi_kursi', 'cakupan_wilayah', 'aksi_caleg']
    list_per_page = 10
    list_display_links = None
    filter_horizontal = ['wilayah']
    search_fields = ['nama']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('wilayah')

    def cakupan_wilayah(self, obj):
        """Daftar Kabupaten/Kota dalam Dapil RI dengan style badge"""
        kab_list = ", ".join([w.nama for w in obj.wilayah.all()])
        if not kab_list: return format_html('<span class="text-muted small">-</span>')
        
        return format_html(
            '<div style="max-width: 350px; line-height: 1.4;">'
            '<span class="badge badge-secondary" style="font-size: 9px;">KABUPATEN / KOTA</span><br>'
            '<span class="text-dark small">{}</span>'
            '</div>', kab_list
        )
    cakupan_wilayah.short_description = "Cakupan Wilayah"

    def aksi_caleg(self, obj):
        """Tombol Aksi Khusus untuk Caleg DPR RI"""
        from django.urls import reverse
        url = reverse('admin:pemilu2024_calegri_changelist')
        
        btn_style = "width: 130px; margin-bottom: 4px; font-weight: bold; text-align: center; display: block;"
        
        btn_all = format_html(
            '<a class="btn btn-sm btn-info" href="{}?dapil__id__exact={}" style="{}">'
            '<i class="fas fa-users"></i> Semua Caleg</a>',
            url, obj.id, btn_style
        )
        
        btn_gerindra = format_html(
            '<a class="btn btn-sm btn-danger" href="{}?dapil__id__exact={}&partai__nama_partai__icontains=GERINDRA" style="{}">'
            '<i class="fas fa-star"></i> Caleg Gerindra</a>',
            url, obj.id, btn_style
        )
        
        return format_html('<div style="display: flex; flex-direction: column; align-items: center; min-width: 140px;">{}{}</div>', btn_all, btn_gerindra)
    aksi_caleg.short_description = "Aksi Monitoring"

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # PENGATURAN IZIN (Ubah ke True kalau mau Edit/Tambah/Hapus lagi)
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# --- 2.3 DAPIL PROVINSI ---
class DapilProvinsiAdminForm(forms.ModelForm):
    class Meta:
        model = DapilProvinsi
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        used_ids = DapilProvinsi.objects.exclude(pk=self.instance.pk if self.instance.pk else None).values_list('wilayah', flat=True)
        self.fields['wilayah'].queryset = KabupatenKota.objects.exclude(id__in=used_ids).order_by('nama')
    def clean_wilayah(self):
        wilayah = self.cleaned_data.get('wilayah')
        for kab in wilayah:
            query = DapilProvinsi.objects.filter(wilayah=kab)
            if self.instance.pk: query = query.exclude(pk=self.instance.pk)
            if query.exists(): raise forms.ValidationError(f"{kab.nama} sudah masuk di Dapil Provinsi {query.first().nama}")
        return wilayah

@admin.register(DapilProvinsi)
class DapilProvinsiAdmin(admin.ModelAdmin):
    form = DapilProvinsiAdminForm
    list_display = ['nama', 'alokasi_kursi', 'cakupan_wilayah', 'aksi_caleg']
    list_per_page = 10
    list_display_links = None
    filter_horizontal = ['wilayah']
    search_fields = ['nama']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('wilayah')

    def cakupan_wilayah(self, obj):
        """Daftar Kabupaten/Kota dalam Dapil Provinsi dengan style badge"""
        kab_list = ", ".join([w.nama for w in obj.wilayah.all()])
        if not kab_list: return format_html('<span class="text-muted small">-</span>')
        
        return format_html(
            '<div style="max-width: 350px; line-height: 1.4;">'
            '<span class="badge badge-secondary" style="font-size: 9px;">KABUPATEN / KOTA</span><br>'
            '<span class="text-dark small">{}</span>'
            '</div>', kab_list
        )
    cakupan_wilayah.short_description = "Cakupan Wilayah"

    def aksi_caleg(self, obj):
        """Tombol Aksi Khusus untuk Caleg Provinsi"""
        from django.urls import reverse
        url = reverse('admin:pemilu2024_calegprovinsi_changelist')
        
        btn_style = "width: 130px; margin-bottom: 4px; font-weight: bold; text-align: center; display: block;"
        
        btn_all = format_html(
            '<a class="btn btn-sm btn-info" href="{}?dapil__id__exact={}" style="{}">'
            '<i class="fas fa-users"></i> Semua Caleg</a>',
            url, obj.id, btn_style
        )
        
        btn_gerindra = format_html(
            '<a class="btn btn-sm btn-danger" href="{}?dapil__id__exact={}&partai__nama_partai__icontains=GERINDRA" style="{}">'
            '<i class="fas fa-star"></i> Caleg Gerindra</a>',
            url, obj.id, btn_style
        )
        
        return format_html('<div style="display: flex; flex-direction: column; align-items: center; min-width: 140px;">{}{}</div>', btn_all, btn_gerindra)
    aksi_caleg.short_description = "Aksi Monitoring"

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # PENGATURAN IZIN (Ubah ke True kalau mau Edit/Tambah/Hapus lagi)
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# --- 2.4 DAPIL KAB/KOTA ---
class DapilKabKotaResource(resources.ModelResource):
    kabupaten = fields.Field(column_name='kabupaten', attribute='kabupaten', widget=widgets.ForeignKeyWidget(KabupatenKota, 'nama'))
    wilayah_kecamatan = fields.Field(column_name='wilayah_kecamatan', attribute='wilayah_kecamatan', widget=widgets.ManyToManyWidget(Kecamatan, field='nama', separator=','))
    wilayah_desa = fields.Field(column_name='wilayah_desa', attribute='wilayah_desa', widget=widgets.ManyToManyWidget(KelurahanDesa, field='desa_kelurahan', separator=','))
    class Meta:
        model = DapilKabKota
        fields = ('kabupaten', 'nama', 'alokasi_kursi', 'wilayah_kecamatan', 'wilayah_desa')
        export_order = ('kabupaten', 'nama', 'alokasi_kursi', 'wilayah_kecamatan', 'wilayah_desa')
        import_id_fields = ['kabupaten', 'nama']
        skip_unchanged = True

class DapilKabKotaAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['wilayah_desa'].label_from_instance = lambda obj: f"{obj.desa_kelurahan} (Kec. {obj.kecamatan.nama})"
        self.fields['wilayah_kecamatan'].queryset = Kecamatan.objects.none()
        self.fields['wilayah_desa'].queryset = KelurahanDesa.objects.none()
        kabupaten_id = self.instance.kabupaten.id if self.instance and self.instance.pk and self.instance.kabupaten else None
        if not kabupaten_id and 'kabupaten' in self.data:
            try: kabupaten_id = int(self.data.get('kabupaten'))
            except (ValueError, TypeError): pass
        if kabupaten_id:
            self.fields['wilayah_kecamatan'].queryset = Kecamatan.objects.filter(kabupaten_kota_id=kabupaten_id).order_by('nama')
            self.fields['wilayah_desa'].queryset = KelurahanDesa.objects.filter(kabupaten_id=kabupaten_id).order_by('kecamatan__nama', 'desa_kelurahan')
    def clean(self):
        cleaned_data = super().clean()
        kab, kecs, desas, inst_id = cleaned_data.get('kabupaten'), cleaned_data.get('wilayah_kecamatan'), cleaned_data.get('wilayah_desa'), self.instance.pk
        if not kab: return cleaned_data
        if kecs:
            for kec in kecs:
                if kec.kabupaten_kota != kab: self.add_error('wilayah_kecamatan', f"Kecamatan {kec.nama} bukan bagian dari {kab.nama}")
                bentrok = DapilKabKota.objects.filter(wilayah_kecamatan=kec).exclude(pk=inst_id).first()
                if bentrok: self.add_error('wilayah_kecamatan', f"Kecamatan {kec.nama} sudah masuk Dapil {bentrok.nama}")
                bentrok_desa = DapilKabKota.objects.filter(wilayah_desa__kecamatan=kec).exclude(pk=inst_id).first()
                if bentrok_desa: self.add_error('wilayah_kecamatan', f"Kecamatan {kec.nama} tidak bisa dipilih karena desanya sudah di Dapil {bentrok_desa.nama}")
        if desas:
            for desa in desas:
                if desa.kabupaten != kab: self.add_error('wilayah_desa', f"Desa {desa.desa_kelurahan} bukan bagian dari {kab.nama}")
                bentrok = DapilKabKota.objects.filter(wilayah_desa=desa).exclude(pk=inst_id).first()
                if bentrok: self.add_error('wilayah_desa', f"Desa {desa.desa_kelurahan} sudah masuk Dapil {bentrok.nama}")
                bentrok_kec = DapilKabKota.objects.filter(wilayah_kecamatan=desa.kecamatan).exclude(pk=inst_id).first()
                if bentrok_kec: self.add_error('wilayah_desa', f"Desa {desa.desa_kelurahan} tidak bisa dipilih karena Kec. {desa.kecamatan.nama} sudah masuk utuh ke Dapil {bentrok_kec.nama}")
        return cleaned_data

@admin.register(DapilKabKota)
class DapilKabKotaAdmin(admin.ModelAdmin):
    form = DapilKabKotaAdminForm
    list_display = ['info_dapil', 'alokasi_kursi', 'cakupan_wilayah', 'aksi_caleg']
    list_per_page = 10
    list_display_links = None
    list_filter = ['kabupaten']
    search_fields = ['nama', 'kabupaten__nama']
    autocomplete_fields = ['kabupaten']
    filter_horizontal = ['wilayah_kecamatan', 'wilayah_desa']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('kabupaten').prefetch_related(
            'wilayah_kecamatan', 
            'wilayah_desa__kecamatan'
        )

    def info_dapil(self, obj):
        """Menampilkan Nama Dapil dan Kabupaten dengan style native Jazzmin"""
        return format_html(
            '<div style="line-height: 1.2;">'
            '<strong class="text-primary" style="font-size: 14px;">{}</strong><br>'
            '<span class="text-muted small" style="font-weight: 600;">{}</span>'
            '</div>',
            obj.nama.upper(),
            obj.kabupaten.nama if obj.kabupaten else "-"
        )
    info_dapil.short_description = "Wilayah Dapil"
    info_dapil.admin_order_field = 'nama'

    def cakupan_wilayah(self, obj):
        """Gabungan Kecamatan & Desa (dengan keterangan Kecamatan dalam kurung)"""
        kec_list = ", ".join([k.nama for k in obj.wilayah_kecamatan.all()])
        
        # Desa sekarang menampilkan (Kecamatan) di belakangnya biar informatif
        desa_list = ", ".join([f"{d.desa_kelurahan} ({d.kecamatan.nama})" for d in obj.wilayah_desa.all()])
        
        content = []
        if kec_list:
            content.append(format_html(
                '<div class="mb-1">'
                '<span class="badge badge-secondary" style="font-size: 9px;">KECAMATAN</span><br>'
                '<span class="text-dark small">{}</span>'
                '</div>', kec_list
            ))
        
        if desa_list:
            content.append(format_html(
                '<div class="mt-2">'
                '<span class="badge badge-info" style="font-size: 9px;">DESA / KELURAHAN (KEC)</span><br>'
                '<span class="text-info small" style="font-style: italic;">{}</span>'
                '</div>', desa_list
            ))
            
        if not content:
            return format_html('<span class="text-muted small">-</span>')
            
        return format_html('<div style="max-width: 380px; line-height: 1.4;">{}</div>', format_html("".join(map(str, content))))
    cakupan_wilayah.short_description = "Cakupan Wilayah"

    def aksi_caleg(self, obj):
        """Tombol Aksi Solid & Gagah (Style Jazzmin Native)"""
        from django.urls import reverse
        url = reverse('admin:pemilu2024_calegkabkota_changelist')
        
        # Pake btn-sm dan Solid Colors (btn-info & btn-danger)
        btn_style = "width: 130px; font-weight: bold; text-align: center; margin-bottom: 4px; display: block;"
        
        # Link 1: Semua Caleg (Warna Biru Info Solid)
        btn_all = format_html(
            '<a class="btn btn-sm btn-info" href="{}?dapil__id__exact={}" style="{}">'
            '<i class="fas fa-users"></i> Semua Caleg</a>',
            url, obj.id, btn_style
        )
        
        # Link 2: Khusus Gerindra (Warna Merah Cerah Solid)
        btn_gerindra = format_html(
            '<a class="btn btn-sm btn-danger" href="{}?dapil__id__exact={}&partai__nama_partai__icontains=GERINDRA" style="{}">'
            '<i class="fas fa-star"></i> Caleg Gerindra</a>',
            url, obj.id, btn_style
        )
        
        return format_html('<div style="display: flex; flex-direction: column; align-items: center; min-width: 140px;">{}{}</div>', btn_all, btn_gerindra)
    aksi_caleg.short_description = "Aksi Monitoring"

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # PENGATURAN IZIN (Ubah ke True kalau mau Edit/Tambah/Hapus lagi)
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# --- 2.5 CALEG (ALL LEVELS) ---
class CalegRIResource(resources.ModelResource):
    partai = fields.Field(column_name='partai', attribute='partai', widget=widgets.ForeignKeyWidget(Partai, 'nama_partai'))
    dapil = fields.Field(column_name='dapil', attribute='dapil', widget=widgets.ForeignKeyWidget(DapilRI, 'nama'))
    class Meta:
        model = CalegRI
        fields = ('dapil', 'partai', 'nomor_urut', 'nama', 'jenis_kelamin')
        export_order = ('dapil', 'partai', 'nomor_urut', 'nama', 'jenis_kelamin')
        import_id_fields = ['dapil', 'partai', 'nomor_urut']
        skip_unchanged = True

@admin.register(CalegRI)
class CalegRIAdmin(ImportExportModelAdmin):
    resource_class = CalegRIResource
    list_display = ['nama_caleg', 'gender_info', 'dapil', 'partai_info']
    list_filter = ['dapil', 'partai', 'jenis_kelamin']
    search_fields = ['nama', 'partai__nama_partai', 'dapil__nama']
    autocomplete_fields = ['partai', 'dapil']
    ordering = ['dapil', 'partai', 'nomor_urut']
    formats = [XLSX]
    def get_queryset(self, request): return super().get_queryset(request).select_related('partai', 'dapil')
    def gender_info(self, obj):
        color = "#2196F3" if obj.jenis_kelamin == 'L' else "#E91E63"
        return format_html('<strong style="color: {}; font-size: 14px;">{}</strong>', color, obj.jenis_kelamin)
    def nama_caleg(self, obj):
        img_html = f'<img src="{obj.foto.url}" width="40" height="40" style="object-fit:cover; border-radius:4px; margin-right:10px;" />' if obj.foto else '<div style="width:40px; height:40px; background:#f5f5f5; border:1px solid #ddd; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; margin-right:10px; color:#999; font-size:9px;">No Foto</div>'
        return format_html('<div style="display:flex; align-items:center;">{}<div style="display:flex; flex-direction:column;"><strong>{}</strong><span style="color:#666; font-size:12px;">No. Urut: {}</span></div></div>', format_html(img_html), obj.nama, obj.nomor_urut)
    def partai_info(self, obj):
        logo_html = f'<img src="{obj.partai.logo.url}" width="30" height="30" style="object-fit:contain; margin-right:5px;" />' if obj.partai.logo else ""
        return format_html('<div style="display:flex; align-items:center;"><strong style="margin-right:8px; font-size:14px;">{}</strong>{}<span>{}</span></div>', obj.partai.no_urut, format_html(logo_html), obj.partai.nama_partai)
    nama_caleg.short_description = "Nama Caleg"
    gender_info.short_description = "L/P"
    partai_info.short_description = "Partai"

    def lookup_allowed(self, lookup, value):
        if lookup in ('partai__nama_partai__icontains', 'dapil__id__exact'):
            return True
        return super().lookup_allowed(lookup, value)

class CalegProvinsiResource(resources.ModelResource):
    partai = fields.Field(column_name='partai', attribute='partai', widget=widgets.ForeignKeyWidget(Partai, 'nama_partai'))
    dapil = fields.Field(column_name='dapil', attribute='dapil', widget=widgets.ForeignKeyWidget(DapilProvinsi, 'nama'))
    class Meta:
        model = CalegProvinsi
        fields = ('dapil', 'partai', 'nomor_urut', 'nama', 'jenis_kelamin')
        export_order = ('dapil', 'partai', 'nomor_urut', 'nama', 'jenis_kelamin')
        import_id_fields = ['dapil', 'partai', 'nomor_urut']
        skip_unchanged = True

@admin.register(CalegProvinsi)
class CalegProvinsiAdmin(ImportExportModelAdmin):
    resource_class = CalegProvinsiResource
    list_display = ['nama_caleg', 'gender_info', 'dapil', 'partai_info']
    list_filter = ['dapil', 'partai', 'jenis_kelamin']
    search_fields = ['nama', 'partai__nama_partai', 'dapil__nama']
    autocomplete_fields = ['partai', 'dapil']
    ordering = ['dapil', 'partai', 'nomor_urut']
    formats = [XLSX]
    def get_queryset(self, request): return super().get_queryset(request).select_related('partai', 'dapil')
    def gender_info(self, obj):
        color = "#2196F3" if obj.jenis_kelamin == 'L' else "#E91E63"
        return format_html('<strong style="color: {}; font-size: 14px;">{}</strong>', color, obj.jenis_kelamin)
    def nama_caleg(self, obj):
        img_html = f'<img src="{obj.foto.url}" width="40" height="40" style="object-fit:cover; border-radius:4px; margin-right:10px;" />' if obj.foto else '<div style="width:40px; height:40px; background:#f5f5f5; border:1px solid #ddd; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; margin-right:10px; color:#999; font-size:9px;">No Foto</div>'
        return format_html('<div style="display:flex; align-items:center;">{}<div style="display:flex; flex-direction:column;"><strong>{}</strong><span style="color:#666; font-size:12px;">No. Urut: {}</span></div></div>', format_html(img_html), obj.nama, obj.nomor_urut)
    def partai_info(self, obj):
        logo_html = f'<img src="{obj.partai.logo.url}" width="30" height="30" style="object-fit:contain; margin-right:5px;" />' if obj.partai.logo else ""
        return format_html('<div style="display:flex; align-items:center;"><strong style="margin-right:8px; font-size:14px;">{}</strong>{}<span>{}</span></div>', obj.partai.no_urut, format_html(logo_html), obj.partai.nama_partai)
    nama_caleg.short_description = "Nama Caleg"
    gender_info.short_description = "L/P"
    partai_info.short_description = "Partai"

    def lookup_allowed(self, lookup, value):
        if lookup in ('partai__nama_partai__icontains', 'dapil__id__exact'):
            return True
        return super().lookup_allowed(lookup, value)

class CalegKabKotaResource(resources.ModelResource):
    partai = fields.Field(column_name='partai', attribute='partai', widget=widgets.ForeignKeyWidget(Partai, 'nama_partai'))
    dapil = fields.Field(column_name='dapil', attribute='dapil', widget=widgets.ForeignKeyWidget(DapilKabKota, 'nama'))
    class Meta:
        model = CalegKabKota
        fields = ('dapil', 'partai', 'nomor_urut', 'nama', 'jenis_kelamin')
        export_order = ('dapil', 'partai', 'nomor_urut', 'nama', 'jenis_kelamin')
        import_id_fields = ['dapil', 'partai', 'nomor_urut']
        skip_unchanged = True

@admin.register(CalegKabKota)
class CalegKabKotaAdmin(ImportExportModelAdmin):
    resource_class = CalegKabKotaResource
    list_display = ['nama_caleg', 'gender_info', 'dapil', 'partai_info']
    list_filter = ['dapil__kabupaten', 'dapil', 'partai', 'jenis_kelamin']
    search_fields = ['nama', 'partai__nama_partai', 'dapil__nama']
    autocomplete_fields = ['partai', 'dapil']
    ordering = ['dapil', 'partai', 'nomor_urut']
    formats = [XLSX]
    def get_queryset(self, request): return super().get_queryset(request).select_related('partai', 'dapil', 'dapil__kabupaten')
    def gender_info(self, obj):
        color = "#2196F3" if obj.jenis_kelamin == 'L' else "#E91E63"
        return format_html('<strong style="color: {}; font-size: 14px;">{}</strong>', color, obj.jenis_kelamin)
    def nama_caleg(self, obj):
        img_html = f'<img src="{obj.foto.url}" width="40" height="40" style="object-fit:cover; border-radius:4px; margin-right:10px;" />' if obj.foto else '<div style="width:40px; height:40px; background:#f5f5f5; border:1px solid #ddd; border-radius:4px; display:inline-flex; align-items:center; justify-content:center; margin-right:10px; color:#999; font-size:9px;">No Foto</div>'
        return format_html('<div style="display:flex; align-items:center;">{}<div style="display:flex; flex-direction:column;"><strong>{}</strong><span style="color:#666; font-size:12px;">No. Urut: {}</span></div></div>', format_html(img_html), obj.nama, obj.nomor_urut)
    def partai_info(self, obj):
        logo_html = f'<img src="{obj.partai.logo.url}" width="30" height="30" style="object-fit:contain; margin-right:5px;" />' if obj.partai.logo else ""
        return format_html('<div style="display:flex; align-items:center;"><strong style="margin-right:8px; font-size:14px;">{}</strong>{}<span>{}</span></div>', obj.partai.no_urut, format_html(logo_html), obj.partai.nama_partai)
    nama_caleg.short_description = "Nama Caleg"
    gender_info.short_description = "L/P"
    partai_info.short_description = "Partai"
    def lookup_allowed(self, lookup, value):
        if lookup in ('partai__nama_partai__icontains', 'dapil__id__exact'):
            return True
        return super().lookup_allowed(lookup, value)   


# =========================================================================
# BAGIAN 3: MONITORING & HASIL PEMILU (PILPRES)
# =========================================================================

# --- 3.1 DATA TPS & DPT KECAMATAN (RESOURCE & ADMIN) ---
class RekapTPSDPTKecamatanResource(resources.ModelResource):
    kabupaten = fields.Field(column_name='kabupaten', attribute='kecamatan__kabupaten_kota__nama', readonly=True)
    kecamatan = fields.Field(
        column_name='kecamatan', 
        attribute='kecamatan', 
        widget=SmartKecamatanWidget(Kecamatan, 'nama')
    )
    class Meta:
        model = RekapTPSDPTKecamatan
        fields = ('id', 'kecamatan', 'tps_pemilu', 'dpt_pemilu')
        import_id_fields = ['kecamatan']
        skip_unchanged = True

@admin.register(RekapTPSDPTKecamatan)
class RekapTPSDPTKecamatanAdmin(ImportExportModelAdmin):
    resource_class = RekapTPSDPTKecamatanResource
    list_display = ['kecamatan', 'kabupaten', 'tps_pemilu', 'dpt_pemilu']
    list_filter = ['kecamatan__kabupaten_kota']
    search_fields = ['kecamatan__nama']
    formats = [XLSX]
    def kabupaten(self, obj): return obj.kecamatan.kabupaten_kota.nama

# --- 3.2 HASIL PILPRES KECAMATAN (RESOURCE & ADMIN) ---
class SuaraPilpresKecamatanResource(resources.ModelResource):
    kabupaten = fields.Field(column_name='kabupaten', attribute='kecamatan__kabupaten_kota__nama', readonly=True)
    kecamatan = fields.Field(
        column_name='kecamatan', 
        attribute='kecamatan', 
        widget=SmartKecamatanWidget(Kecamatan, 'nama')
    )
    class Meta:
        model = SuaraPilpresKecamatan
        fields = ('id', 'kecamatan', 'suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah')
        import_id_fields = ['kecamatan']
        skip_unchanged = True

@admin.register(SuaraPilpresKecamatan)
class SuaraPilpresKecamatanAdmin(ImportExportModelAdmin):
    resource_class = SuaraPilpresKecamatanResource
    list_display = ['kecamatan', 'kabupaten', 'suara_paslon_1', 'suara_paslon_2', 'suara_paslon_3', 'suara_tidak_sah']
    list_filter = ['kecamatan__kabupaten_kota']
    search_fields = ['kecamatan__nama']
    formats = [XLSX]
    def kabupaten(self, obj): return obj.kecamatan.kabupaten_kota.nama

# --- 3.3 DATA TPS & DPT DESA (RESOURCE) ---
class SmartDesaWidget(widgets.ForeignKeyWidget):
    """Widget khusus untuk mencari Desa berdasarkan Nama, Kecamatan, dan Kabupaten-nya"""
    def clean(self, value, row=None, **kwargs):
        kab, kec = row.get('kabupaten') or row.get('kabupaten_kota'), row.get('kecamatan')
        if value and kab and kec: return self.model.objects.get(desa_kelurahan=value, kecamatan__nama=kec, kabupaten__nama=kab)
        return super().clean(value, row, **kwargs)

class RekapTPSDPTResource(resources.ModelResource):
    kabupaten = fields.Field(column_name='kabupaten', attribute='desa__kabupaten__nama', readonly=True)
    kecamatan = fields.Field(column_name='kecamatan', attribute='desa__kecamatan__nama', readonly=True)
    desa = fields.Field(column_name='desa', attribute='desa', widget=SmartDesaWidget(KelurahanDesa, 'desa_kelurahan'))
    class Meta:
        model = RekapTPSDPT
        fields = ('id', 'desa', 'tps_pemilu', 'dpt_pemilu')
        import_id_fields = ['desa']
        skip_unchanged = True
        follow_relations = True
    def before_import(self, dataset, **kwargs):
        mapping = {'kabupaten_kota': 'kabupaten', 'desa_kelurahan': 'desa', 'jumlah_tps': 'tps_pemilu', 'jumlah_dpt': 'dpt_pemilu'}
        new_headers = []
        for h in dataset.headers:
            low = str(h).lower().strip(); found = False
            for alt, off in mapping.items():
                if low == alt: new_headers.append(off); found = True; break
            if not found: new_headers.append(h)
        dataset.headers = new_headers

# --- 3.2 PASLON PILPRES ---
class PaslonPilpresResource(resources.ModelResource):
    class Meta:
        model = PaslonPilpres
        fields = ('no_urut', 'nama_capres', 'nama_cawapres', 'foto_paslon')
        export_order = ('no_urut', 'nama_capres', 'nama_cawapres', 'foto_paslon')
        import_id_fields = ['no_urut']
        skip_unchanged = True
        report_skipped = True

class PaslonPilpresAdminForm(forms.ModelForm):
    class Meta:
        model = PaslonPilpres
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        used = PaslonPilpres.objects.exclude(pk=self.instance.pk if self.instance.pk else None).values_list('koalisi', flat=True)
        avail = Partai.objects.exclude(id__in=used)
        if self.instance.pk: avail = (avail | self.instance.koalisi.all()).distinct()
        self.fields['koalisi'].queryset = avail.order_by('no_urut')

@admin.register(PaslonPilpres)
class PaslonPilpresAdmin(ImportExportModelAdmin, PaslonAdminMixin):
    resource_class = PaslonPilpresResource
    form = PaslonPilpresAdminForm
    list_display = ['info_paslon', 'koalisi_partai']
    list_display_links = ['info_paslon']
    ordering = ['no_urut']
    filter_horizontal = ['koalisi']
    search_fields = ['nama_capres', 'nama_cawapres']
    formats = [XLSX]
    def get_queryset(self, request): return super().get_queryset(request).prefetch_related('koalisi')
    def save_model(self, request, obj, form, change): super().save_model(request, obj, form, change); clear_paslon_cache()
    def info_paslon(self, obj):
        return format_html('<div style="display: flex; align-items: center; gap: 10px;">{}<div><strong style="font-size: 14px;">{} - {}</strong><br><small style="color: #666;">No. Urut: {}</small></div></div>', format_html(self.get_image_preview(obj.foto_paslon)), obj.nama_capres, obj.nama_cawapres, obj.no_urut)
    info_paslon.short_description = "Pasangan Calon"


# =========================================================================
# BAGIAN 4: DATA HASIL (PILKADA)
# =========================================================================

class PaslonPilkadaResource(resources.ModelResource):
    class Meta:
        model = PaslonPilkada
        fields = ('jenis_pilkada', 'kabupaten_kota', 'no_urut', 'nama_cakada', 'nama_cawakada', 'foto_paslon')
        export_order = ('jenis_pilkada', 'kabupaten_kota', 'no_urut', 'nama_cakada', 'nama_cawakada', 'foto_paslon')
        import_id_fields = ['jenis_pilkada', 'kabupaten_kota', 'no_urut']
        skip_unchanged = True
        report_skipped = True

class PaslonPilkadaAdminForm(forms.ModelForm):
    class Meta:
        model = PaslonPilkada
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance.pk:
            target_jenis = self.instance.jenis_pilkada
            target_kk = self.instance.kabupaten_kota_id
        else:
            target_jenis = self.data.get('jenis_pilkada') or self.initial.get('jenis_pilkada') or 'KOKAB'
            target_kk = self.data.get('kabupaten_kota') or self.initial.get('kabupaten_kota')

        if target_jenis == 'PROV':
            others_qs = PaslonPilkada.objects.filter(jenis_pilkada='PROV')
        elif target_jenis == 'KOKAB' and target_kk:
            others_qs = PaslonPilkada.objects.filter(jenis_pilkada='KOKAB', kabupaten_kota_id=target_kk)
        else:
            others_qs = PaslonPilkada.objects.none()

        if self.instance.pk:
            others_qs = others_qs.exclude(pk=self.instance.pk)

        used_party_ids = set()
        for p_id in others_qs.values_list('koalisi', flat=True):
            if p_id:
                used_party_ids.add(p_id)

        available_qs = Partai.objects.exclude(id__in=used_party_ids)
        if self.instance.pk:
            current_parties = self.instance.koalisi.all()
            available_qs = (available_qs | current_parties).distinct()

        self.fields['koalisi'].queryset = available_qs.order_by('no_urut')
        self.fields['nama_cawakada'].required = False

    def clean(self):
        cleaned_data = super().clean()
        nama_cakada = cleaned_data.get('nama_cakada')
        nama_cawakada = cleaned_data.get('nama_cawakada')

        if nama_cakada and nama_cakada.upper() == 'KOTAK KOSONG':
            if not nama_cawakada:
                cleaned_data['nama_cawakada'] = '-'
        elif not nama_cawakada:
            self.add_error('nama_cawakada', 'Field ini wajib diisi kecuali untuk KOTAK KOSONG.')

        jenis_pilkada = cleaned_data.get('jenis_pilkada')
        kabupaten_kota = cleaned_data.get('kabupaten_kota')

        if jenis_pilkada and (kabupaten_kota or jenis_pilkada == 'PROV'):
            koalisi = cleaned_data.get('koalisi')
            if koalisi:
                if jenis_pilkada == 'PROV':
                    others = PaslonPilkada.objects.filter(jenis_pilkada='PROV')
                else:
                    others = PaslonPilkada.objects.filter(jenis_pilkada='KOKAB', kabupaten_kota=kabupaten_kota)

                if self.instance.pk:
                    others = others.exclude(pk=self.instance.pk)
                
                used_party_ids = set()
                for other in others:
                    used_party_ids.update(other.koalisi.all().values_list('id', flat=True))
                
                for party in koalisi:
                    if party.id in used_party_ids:
                        self.add_error('koalisi', f"Partai {party.nama_partai} sudah terdaftar di Paslon lain untuk wilayah ini.")

        return cleaned_data

@admin.register(PaslonPilkada)
class PaslonPilkadaAdmin(ImportExportModelAdmin, PaslonAdminMixin):
    resource_class = PaslonPilkadaResource
    form = PaslonPilkadaAdminForm
    list_display = ['info_paslon', 'koalisi_partai']
    list_display_links = ['info_paslon']
    ordering = ['jenis_pilkada', 'kabupaten_kota', 'no_urut']
    filter_horizontal = ['koalisi']
    list_filter = ['jenis_pilkada', 'kabupaten_kota']
    search_fields = ['kabupaten_kota__nama', 'nama_cakada', 'nama_cawakada']
    formats = [XLSX]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('kabupaten_kota').prefetch_related('koalisi')

    class Media:
        js = ('admin/js/pilkada_admin.js',)
    
    fieldsets = (
        ('Jenis & Wilayah', {'fields': ('jenis_pilkada', 'kabupaten_kota')}),
        ('Data Pasangan Calon', {'fields': ('no_urut', 'nama_cakada', 'nama_cawakada', 'foto_paslon')}),
        ('Partai Pendukung', {'fields': ('koalisi',)}),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        if 'jenis_pilkada' in request.GET:
            initial['jenis_pilkada'] = request.GET.get('jenis_pilkada')
        if 'kabupaten_kota' in request.GET:
            initial['kabupaten_kota'] = request.GET.get('kabupaten_kota')
        return initial

    def info_paslon(self, obj):
        if obj.jenis_pilkada == 'PROV':
            wilayah_html = '<span style="background: #800000; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-right: 5px;">PROVINSI</span> JAWA BARAT'
        else:
            wilayah_text = str(obj.kabupaten_kota) if obj.kabupaten_kota else "-"
            wilayah_html = f'<span style="background: #333; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-right: 5px;">KAB/KOTA</span> {wilayah_text}'

        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<div>{}</div>'
            '<div>'
            '<strong style="font-size: 14px;">{} - {}</strong><br>'
            '<small style="color: #666;">{} | No. Urut: {}</small>'
            '</div>'
            '</div>',
            format_html(self.get_image_preview(obj.foto_paslon)),
            obj.nama_cakada,
            obj.nama_cawakada,
            format_html(wilayah_html),
            obj.no_urut
        )
    info_paslon.short_description = "Pasangan Calon"

# =========================================================================
# BAGIAN 4: GEOSPATIAL ADMIN (PETA DIGITAL)
# =========================================================================

class GeoColorForm(forms.ModelForm):
    """Form khusus untuk menambahkan Color Picker"""
    class Meta:
        widgets = {
            'warna_area': forms.TextInput(attrs={'type': 'color', 'style': 'height: 40px; width: 100px; cursor: pointer; border: none; padding: 2px; background: none;'}),
        }

class GeoAdminMixin:
    """Mixin untuk fungsi bersama antara data geospatial (Kokab, Kec, Deskel)"""
    
    def changelist_view(self, request, extra_context=None):
        """Menambahkan tombol besar di bagian atas list view (Main Dashboard)"""
        extra_context = extra_context or {}
        extra_context['dashboard_button_html'] = format_html(
            '<div style="margin-bottom: 20px; padding: 15px; background: #FFF9E6; border: 1px solid #D4AF37; border-radius: 12px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">'
            '<div><strong style="font-size: 18px; color: #800000; display: flex; align-items: center; gap: 10px;">'
            '<span style="background: #800000; color: white; padding: 5px 10px; border-radius: 8px; font-size: 14px;">PRO</span> WAR ROOM - PETA DIGITAL</strong>'
            '<p style="margin: 5px 0 0 0; color: #555; font-size: 13px;">Klik tombol di samping untuk beralih ke Dashboard Peta Interaktif (Full Screen).</p></div>'
            '<a href="/map/" target="_blank" style="background: #800000; color: white !important; padding: 12px 25px; font-weight: 700; border-radius: 8px; text-decoration: none; display: flex; align-items: center; gap: 10px; transition: all 0.3s; border: 1px solid #D4AF37;">'
            '🌍 BUKA PETA ANALISIS</a>'
            '</div>'
        )
        return super().changelist_view(request, extra_context=extra_context)

    def preview_peta(self, obj):
        if not obj or not obj.vektor_wilayah:
            return "Belum ada data vektor untuk ditampilkan."
        
        import json
        from django.utils.safestring import mark_safe
        
        try:
            clean_data = json.loads(obj.vektor_wilayah)
            clean_json = json.dumps(clean_data)
        except Exception as e:
            return format_html('<span style="color: red;">Format GeoJSON Error: {}</span>', str(e))

        map_id = f"map_{obj.id or 'new'}"
        return format_html(
            '''
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <div id="{0}" style="height: 450px; width: 100%; border: 2px solid #800000; border-radius: 8px; background: #eee; margin-top: 10px;"></div>
            <script>
                (function() {{
                    var mapLayer;
                    var initCount = 0;
                    var interval = setInterval(function() {{
                        if (window.L) {{
                            clearInterval(interval);
                            initializeMap();
                        }}
                        if (initCount > 50) clearInterval(interval);
                        initCount++;
                    }}, 200);

                    function initializeMap() {{
                        var map = L.map('{0}').setView([0, 0], 2);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                            attribution: '&copy; OpenStreetMap'
                        }}).addTo(map);
                        
                        try {{
                            var geoData = {1};
                            mapLayer = L.geoJSON(geoData, {{
                                style: function(feature) {{
                                    return {{
                                        color: document.getElementById('id_warna_area').value || "{2}",
                                        weight: 3,
                                        fillOpacity: 0.4
                                    }};
                                }}
                            }}).addTo(map);
                            map.fitBounds(mapLayer.getBounds(), {{ padding: [30, 30] }});

                            // LIVE COLOR UPDATE!
                            document.getElementById('id_warna_area').addEventListener('input', function(e) {{
                                if (mapLayer) {{
                                    mapLayer.setStyle({{ color: e.target.value }});
                                }};
                            }});

                        }} catch (e) {{
                            console.error("Leaflet Parse Error:", e);
                        }}
                    }}
                }})();
            </script>
            ''',
            map_id,
            mark_safe(clean_json),
            obj.warna_area or "#CC0000"
        )
    preview_peta.short_description = "Monitor Peta Digital"

@admin.register(GeoKokab)
class GeoKokabAdmin(GeoAdminMixin, admin.ModelAdmin):
    form = GeoColorForm
    list_display = ['kokab', 'warna_area', 'last_update']
    search_fields = ['kokab__nama']
    readonly_fields = ['preview_peta']

@admin.register(GeoKecamatan)
class GeoKecamatanAdmin(GeoAdminMixin, admin.ModelAdmin):
    form = GeoColorForm
    list_display = ['kecamatan', 'warna_area']
    search_fields = ['kecamatan__nama']
    readonly_fields = ['preview_peta']

@admin.register(GeoDesKel)
class GeoDesKelAdmin(GeoAdminMixin, admin.ModelAdmin):
    form = GeoColorForm
    list_display = ['deskel', 'warna_area']
    search_fields = ['deskel__desa_kelurahan']
    readonly_fields = ['preview_peta']
