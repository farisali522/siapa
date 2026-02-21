from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from .models import (
    KabupatenKota, Kecamatan, KelurahanDesa, 
    DapilRI, DapilProvinsi, DapilKabKota, Partai,
    TPSDPTPemilu, TPSDPTPilkada
)

# --- FORMS & WIDGETS ---

class DapilRIForm(forms.ModelForm):
    kabupaten_pilihan = forms.ModelMultipleChoiceField(
        queryset=KabupatenKota.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("Kabupaten/Kota", is_stacked=False),
        label="Cakupan Kabupaten/Kota"
    )
    class Meta:
        model = DapilRI
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['kabupaten_pilihan'].initial = self.instance.kabupaten_set.all()

    def save(self, commit=True):
        instance = super().save(commit=commit)
        instance.kabupaten_set.update(dapil_ri=None)
        kab_pilihan = self.cleaned_data.get('kabupaten_pilihan')
        if kab_pilihan:
            kab_pilihan.update(dapil_ri=instance)
        return instance

class DapilProvinsiForm(forms.ModelForm):
    kabupaten_pilihan = forms.ModelMultipleChoiceField(
        queryset=KabupatenKota.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("Kabupaten/Kota", is_stacked=False),
        label="Cakupan Kabupaten/Kota"
    )
    class Meta:
        model = DapilProvinsi
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['kabupaten_pilihan'].initial = self.instance.kabupaten_set.all()

    def save(self, commit=True):
        instance = super().save(commit=commit)
        instance.kabupaten_set.update(dapil_provinsi=None)
        kab_pilihan = self.cleaned_data.get('kabupaten_pilihan')
        if kab_pilihan:
            kab_pilihan.update(dapil_provinsi=instance)
        return instance

class PartaiForm(forms.ModelForm):
    class Meta:
        model = Partai
        fields = '__all__'
        widgets = {
            'warna_hex': forms.TextInput(attrs={
                'type': 'color', 
                'style': 'width: 150px; height: 45px; cursor: pointer; border-radius: 4px; border: 1px solid #ccc;'
            }),
        }

class KecamatanForm(forms.ModelForm):
    # Gabungkan data TPS/DPT langsung ke form utama (Satu Tab)
    tps_pemilu = forms.IntegerField(label="Total TPS Pemilu", required=False, min_value=0)
    dpt_pemilu = forms.IntegerField(label="DPT Pemilu", required=False, min_value=0)
    
    tps_pilkada = forms.IntegerField(label="Total TPS Pilkada", required=False, min_value=0)
    dpt_pilkada = forms.IntegerField(label="DPT Pilkada", required=False, min_value=0)

    class Meta:
        model = Kecamatan
        fields = ['kabupaten_kota', 'dapil_kab_kota', 'nama']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Ambil data TPS Pemilu
            tps_em, _ = TPSDPTPemilu.objects.get_or_create(kecamatan=self.instance)
            self.fields['tps_pemilu'].initial = tps_em.jumlah_tps
            self.fields['dpt_pemilu'].initial = tps_em.jumlah_dpt
            
            # Ambil data TPS Pilkada
            tps_ak, _ = TPSDPTPilkada.objects.get_or_create(kecamatan=self.instance)
            self.fields['tps_pilkada'].initial = tps_ak.jumlah_tps
            self.fields['dpt_pilkada'].initial = tps_ak.jumlah_dpt

    def save(self, commit=True):
        instance = super().save(commit=commit)
        # Update data TPS Pemilu
        TPSDPTPemilu.objects.update_or_create(
            kecamatan=instance,
            defaults={
                'jumlah_tps': self.cleaned_data.get('tps_pemilu', 0),
                'jumlah_dpt': self.cleaned_data.get('dpt_pemilu', 0),
            }
        )
        # Update data TPS Pilkada
        TPSDPTPilkada.objects.update_or_create(
            kecamatan=instance,
            defaults={
                'jumlah_tps': self.cleaned_data.get('tps_pilkada', 0),
                'jumlah_dpt': self.cleaned_data.get('dpt_pilkada', 0),
            }
        )
        return instance

# --- INLINES ---

class TPSDPTPemiluInline(admin.StackedInline):
    model = TPSDPTPemilu
    can_delete = False
    verbose_name = "Data TPS & DPT Pemilu"
    extra = 0

class TPSDPTPilkadaInline(admin.StackedInline):
    model = TPSDPTPilkada
    can_delete = False
    verbose_name = "Data TPS & DPT Pilkada"
    extra = 0

# --- MASTER DATA ---

@admin.register(Partai)
class PartaiAdmin(admin.ModelAdmin):
    form = PartaiForm
    list_display = ('partai_info', 'color_preview')
    search_fields = ('nama',)
    ordering = ('no_urut',)

    @admin.display(description='Partai')
    def partai_info(self, obj):
        logo_html = ""
        if obj.logo:
            logo_html = format_html(
                '<div style="background: #fff; padding: 2px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); '
                'display: flex; align-items: center; justify-content: center; margin-right: 15px; width: 40px; height: 40px; border: 1px solid #eee;">'
                '<img src="{}" style="max-width: 100%; max-height: 100%; object-fit: contain;" />'
            '</div>', obj.logo.url)
        return format_html(
            '<div style="display: flex; align-items: center; padding: 4px 0;">'
            '<div style="min-width: 30px; height: 30px; background: #333; color: #fff; border-radius: 50%; '
            'display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; '
            'margin-right: 15px;">{}</div>'
            '{} <b>{}</b></div>', obj.no_urut, logo_html, obj.nama
        )

    @admin.display(description='Warna Identitas')
    def color_preview(self, obj):
        return format_html(
            '<div style="display: flex; align-items: center; background: #f8f9fa; padding: 4px 10px; border-radius: 20px; border: 1px solid #ddd; width: fit-content;">'
            '<div style="width: 14px; height: 14px; background: {}; border-radius: 50%; margin-right: 8px; border: 1.5px solid #fff; box-shadow: 0 0 0 1px #ddd;"></div>'
            '<span style="font-family: Courier; font-weight: bold;">{}</span></div>',
            obj.warna_hex, obj.warna_hex
        )

# --- WILAYAH & DAPIL ---

@admin.register(KabupatenKota)
class KabupatenAdmin(admin.ModelAdmin):
    list_display = ('nama', 'dapil_ri', 'dapil_provinsi')
    list_filter = ('dapil_ri', 'dapil_provinsi')
    search_fields = ('nama',)
    autocomplete_fields = ('dapil_ri', 'dapil_provinsi')

@admin.register(Kecamatan)
class KecamatanAdmin(admin.ModelAdmin):
    form = KecamatanForm
    list_display = ('nama', 'kabupaten_kota', 'get_dapil_kab_nama')
    list_filter = ('kabupaten_kota', 'dapil_kab_kota')
    search_fields = ('nama', 'kabupaten_kota__nama')
    autocomplete_fields = ('kabupaten_kota', 'dapil_kab_kota')
    
    # Satu Tab Polos: Sesuai keinginan Bos
    fields = (
        'kabupaten_kota', 'dapil_kab_kota', 'nama',
        'tps_pemilu', 'dpt_pemilu', 
        'tps_pilkada', 'dpt_pilkada'
    )

    def get_queryset(self, request):
        # OPTIMASI: Join table kabupaten sekaligus
        return super().get_queryset(request).select_related('kabupaten_kota', 'dapil_kab_kota')

    @admin.display(description='Dapil Kab/Kota', ordering='dapil_kab_kota__nama')
    def get_dapil_kab_nama(self, obj):
        return obj.dapil_kab_kota.nama if obj.dapil_kab_kota else "-"

@admin.register(KelurahanDesa)
class DesaAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kecamatan', 'get_kabupaten')
    list_filter = ('kecamatan__kabupaten_kota', 'kecamatan')
    search_fields = ('nama',)
    autocomplete_fields = ('kecamatan', 'dapil_kab_kota')

    def get_queryset(self, request):
        # OPTIMASI: Join table kecamatan dan kabupaten sekaligus
        return super().get_queryset(request).select_related('kecamatan', 'kecamatan__kabupaten_kota')

    @admin.display(description='Kabupaten/Kota', ordering='kecamatan__kabupaten_kota')
    def get_kabupaten(self, obj):
        return obj.kecamatan.kabupaten_kota

@admin.register(DapilRI, DapilProvinsi)
class DapilGlobalAdmin(admin.ModelAdmin):
    form = DapilRIForm
    list_display = ('nama', 'kursi', 'get_wilayah')
    search_fields = ('nama',)

    def get_queryset(self, request):
        # OPTIMASI: Prefetch kabupaten agar get_wilayah tidak hit DB berkali-kali
        return super().get_queryset(request).prefetch_related('kabupaten_set')

    @admin.display(description='Cakupan Wilayah')
    def get_wilayah(self, obj):
        return ", ".join([k.nama for k in obj.kabupaten_set.all()])

@admin.register(DapilKabKota)
class DapilKabKotaAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kursi', 'kabupaten_kota', 'get_wilayah')
    list_filter = ('kabupaten_kota',)
    search_fields = ('nama',)

    def get_queryset(self, request):
        # OPTIMASI: Prefetch kecamatan agar get_wilayah tidak hit DB berkali-kali
        return super().get_queryset(request).select_related('kabupaten_kota').prefetch_related('kecamatan_set')

    @admin.display(description='Kecamatan')
    def get_wilayah(self, obj):
        kec = [k.nama for k in obj.kecamatan_set.all()]
        return ", ".join(kec) if kec else "-"
