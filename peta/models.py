from django.db import models
from pemilu2024.models import KabupatenKota, Kecamatan, KelurahanDesa

# ============================================
# GEOSPATIAL MODELS (PETA DIGITAL)
# ============================================

class GeoKokab(models.Model):
    """Data Vektor Batas Wilayah Kabupaten/Kota"""
    kokab = models.OneToOneField(
        KabupatenKota, 
        on_delete=models.CASCADE, 
        related_name='geodata',
        verbose_name="Kabupaten/Kota"
    )
    vektor_wilayah = models.TextField(
        verbose_name="Data Vektor (GeoJSON)", 
        help_text="Paste kode GeoJSON batas wilayah di sini",
        blank=True, null=True
    )
    # Warna default diselujui #800000 (Maroon) tapi biasanya gray defaultnya
    warna_area = models.CharField(max_length=7, default="#808080", verbose_name="Warna Area (Hex)")
    last_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Geo Kokab"
        verbose_name_plural = "Peta Batas Kokab"

    def __str__(self):
        return f"Peta {self.kokab.nama}"

class GeoKecamatan(models.Model):
    """Data Vektor Batas Wilayah Kecamatan"""
    kecamatan = models.OneToOneField(
        Kecamatan, 
        on_delete=models.CASCADE, 
        related_name='geodata',
        verbose_name="Kecamatan"
    )
    vektor_wilayah = models.TextField(
        verbose_name="Data Vektor (GeoJSON)",
        blank=True, null=True
    )
    warna_area = models.CharField(max_length=7, default="#808080", verbose_name="Warna Area (Hex)")

    def get_kab_nama(self):
        return self.kecamatan.kabupaten_kota.nama
    get_kab_nama.short_description = "Kabupaten/Kota"
    get_kab_nama.admin_order_field = 'kecamatan__kabupaten_kota__nama'

    class Meta:
        verbose_name = "Geo Kecamatan"
        verbose_name_plural = "Peta Batas Kecamatan"

    def __str__(self):
        return f"Peta Kec. {self.kecamatan.nama}"

class GeoDesKel(models.Model):
    """Data Vektor Batas Wilayah Desa/Kelurahan"""
    deskel = models.OneToOneField(
        KelurahanDesa, 
        on_delete=models.CASCADE, 
        related_name='geodata',
        verbose_name="Desa/Kelurahan"
    )
    vektor_wilayah = models.TextField(
        verbose_name="Data Vektor (GeoJSON)",
        help_text="Paste kode GeoJSON batas wilayah di sini",
        blank=True, null=True
    )
    warna_area = models.CharField(max_length=7, default="#808080", verbose_name="Warna Area (Hex)")

    # --- Methods for Admin Display ---
    def get_kec_nama(self):
        return self.deskel.kecamatan.nama
    get_kec_nama.short_description = "Kecamatan"
    get_kec_nama.admin_order_field = 'deskel__kecamatan__nama'

    def get_kab_nama(self):
        return self.deskel.kecamatan.kabupaten_kota.nama
    get_kab_nama.short_description = "Kabupaten/Kota"
    get_kab_nama.admin_order_field = 'deskel__kecamatan__kabupaten_kota__nama'

    class Meta:
        verbose_name = "Geo DesKel"
        verbose_name_plural = "Peta Batas DesKel"

    def __str__(self):
        return f"Peta Desa {self.deskel.desa_kelurahan}"
