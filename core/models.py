from django.db import models

# ==============================================================================
# MASTER DATA: PARTAI POLITIK
# ==============================================================================

class Partai(models.Model):
    """
    Menyimpan data partai politik peserta pemilu.
    Atribut utama meliputi nomor urut kpu, nama resmi, logo, dan warna identitas.
    """
    no_urut = models.IntegerField(
        unique=True, 
        verbose_name="No. Urut", 
        db_index=True
    )
    nama = models.CharField(
        max_length=200, 
        verbose_name="Nama Partai", 
        db_index=True
    )
    logo = models.ImageField(
        upload_to='partai_logos/', 
        null=True, 
        blank=True, 
        verbose_name="Logo Partai"
    )
    warna_hex = models.CharField(
        max_length=7, 
        default="#FFFFFF", 
        verbose_name="Warna Identitas (HEX)"
    )

    class Meta:
        verbose_name = "Partai"
        verbose_name_plural = "Data Partai"
        ordering = ['no_urut']

    def __str__(self):
        return f"{self.no_urut}. {self.nama}"


# ==============================================================================
# DATA WILAYAH & GEOGRAFI
# ==============================================================================

class KabupatenKota(models.Model):
    """
    Menyimpan data Kabupaten atau Kota.
    Terhubung langsung ke Dapil RI dan Dapil Provinsi.
    """
    nama = models.CharField(
        max_length=200, 
        verbose_name="Nama Kabupaten/Kota", 
        db_index=True
    )
    dapil_ri = models.ForeignKey(
        'DapilRI', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='kabupaten_set', 
        db_index=True,
        verbose_name="Dapil RI"
    )
    dapil_provinsi = models.ForeignKey(
        'DapilProvinsi', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='kabupaten_set', 
        db_index=True,
        verbose_name="Dapil Provinsi"
    )

    class Meta:
        verbose_name = "Kabupaten/Kota"
        verbose_name_plural = "Data Kabupaten/Kota"
        ordering = ['nama']

    def __str__(self):
        return self.nama


class Kecamatan(models.Model):
    """
    Menyimpan data Kecamatan di bawah Kabupaten/Kota.
    Bisa terhubung ke Dapil Kab/Kota (Dapil Tingkat II).
    """
    kabupaten_kota = models.ForeignKey(
        KabupatenKota, 
        on_delete=models.CASCADE, 
        related_name='kecamatan_set',
        verbose_name="Kabupaten/Kota"
    )
    dapil_kab_kota = models.ForeignKey(
        'DapilKabKota', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='kecamatan_set', 
        db_index=True,
        verbose_name="Dapil Kab/Kota"
    )
    nama = models.CharField(
        max_length=200, 
        verbose_name="Nama Kecamatan", 
        db_index=True
    )

    class Meta:
        verbose_name = "Kecamatan"
        verbose_name_plural = "Data Kecamatan"
        ordering = ['nama']
        unique_together = ('kabupaten_kota', 'nama')

    def __str__(self):
        return self.nama



class KelurahanDesa(models.Model):
    """
    Menyimpan data Kelurahan atau Desa di bawah Kecamatan.
    Bisa memiliki Dapil Kab/Kota yang berbeda jika terjadi pecahan wilayah.
    """
    kecamatan = models.ForeignKey(
        Kecamatan, 
        on_delete=models.CASCADE, 
        related_name='desa_set',
        verbose_name="Kecamatan"
    )
    dapil_kab_kota = models.ForeignKey(
        'DapilKabKota', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='desa_set', 
        db_index=True,
        verbose_name="Dapil Kab/Kota"
    )
    nama = models.CharField(
        max_length=200, 
        verbose_name="Nama Kelurahan/Desa", 
        db_index=True
    )

    class Meta:
        verbose_name = "Kelurahan/Desa"
        verbose_name_plural = "Data Kelurahan/Desa"
        ordering = ['nama']
        unique_together = ('kecamatan', 'nama')

    def __str__(self):
        return self.nama


# ==============================================================================
# DATA DAERAH PEMILIHAN (DAPIL)
# ==============================================================================

class DapilRI(models.Model):
    """
    Daerah Pemilihan untuk tingkat DPR RI.
    Cakupannya adalah kumpulan Kabupaten/Kota.
    """
    nama = models.CharField(max_length=200, verbose_name="Nama Dapil RI", db_index=True)
    kursi = models.IntegerField(default=0, verbose_name="Alokasi Kursi")

    class Meta:
        verbose_name = "Dapil RI"
        verbose_name_plural = "Data Dapil RI"

    def __str__(self):
        return self.nama


class DapilProvinsi(models.Model):
    """
    Daerah Pemilihan untuk tingkat DPRD Provinsi.
    Cakupannya adalah kumpulan Kabupaten/Kota.
    """
    nama = models.CharField(max_length=200, verbose_name="Nama Dapil Provinsi", db_index=True)
    kursi = models.IntegerField(default=0, verbose_name="Alokasi Kursi")

    class Meta:
        verbose_name = "Dapil Provinsi"
        verbose_name_plural = "Data Dapil Provinsi"

    def __str__(self):
        return self.nama


class DapilKabKota(models.Model):
    """
    Daerah Pemilihan untuk tingkat DPRD Kabupaten/Kota.
    Terikat pada satu Kabupaten/Kota tertentu.
    """
    kabupaten_kota = models.ForeignKey(
        KabupatenKota, 
        on_delete=models.CASCADE, 
        related_name='dapil_kab_set',
        verbose_name="Kabupaten/Kota"
    )
    nama = models.CharField(max_length=200, verbose_name="Nama Dapil Kab/Kota", db_index=True)
    kursi = models.IntegerField(default=0, verbose_name="Alokasi Kursi")

    class Meta:
        verbose_name = "Dapil Kab/Kota"
        verbose_name_plural = "Data Dapil Kab/Kota"

    def __str__(self):
        return f"{self.kabupaten_kota} - {self.nama}"


# ==============================================================================
# DATA TPS & DPT (AGREGAT KECAMATAN)
# ==============================================================================

class TPSDPTPemilu(models.Model):
    """
    Data Agregat TPS dan DPT untuk Pemilu Nasional (Pilpres/Pileg).
    Data ini menjadi acuan partisipasi di tingkat Kecamatan.
    """
    kecamatan = models.OneToOneField(
        Kecamatan, 
        on_delete=models.CASCADE, 
        related_name='tpsdpt_pemilu',
        verbose_name="Kecamatan"
    )
    jumlah_tps = models.IntegerField(default=0, verbose_name="Total TPS Pemilu")
    jumlah_dpt = models.IntegerField(default=0, verbose_name="DPT Pemilu Serentak")

    class Meta:
        verbose_name = "Data TPS & DPT Pemilu"
        verbose_name_plural = "Data TPS & DPT Pemilu"

    def __str__(self):
        return f"TPS/DPT Pemilu - {self.kecamatan.nama}"


class TPSDPTPilkada(models.Model):
    """
    Data Agregat TPS dan DPT untuk Pilkada (Gubernur/Bupati/Walikota).
    """
    kecamatan = models.OneToOneField(
        Kecamatan, 
        on_delete=models.CASCADE, 
        related_name='tpsdpt_pilkada',
        verbose_name="Kecamatan"
    )
    jumlah_tps = models.IntegerField(default=0, verbose_name="Total TPS Pilkada")
    jumlah_dpt = models.IntegerField(default=0, verbose_name="DPT Pilkada Serentak")

    class Meta:
        verbose_name = "Data TPS & DPT Pilkada"
        verbose_name_plural = "Data TPS & DPT Pilkada"

    def __str__(self):
        return f"TPS/DPT Pilkada - {self.kecamatan.nama}"
