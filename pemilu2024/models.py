from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import uuid
import os

# Create your models here.

def partai_logo_path(instance, filename):
    """Generate unique filename for partai logo"""
    ext = filename.split('.')[-1]
    filename = f"partai_{instance.no_urut}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('partai_logos', filename)

def paslon_photo_path(instance, filename):
    """Generate unique filename for paslon photo"""
    ext = filename.split('.')[-1]
    filename = f"paslon_{instance.no_urut}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('paslon_photos', filename)

class Partai(models.Model):
    no_urut = models.IntegerField(unique=True, verbose_name="Nomor Urut")
    nama_partai = models.CharField(max_length=200, verbose_name="Nama Partai")
    logo = models.ImageField(upload_to=partai_logo_path, verbose_name="Logo Partai", blank=True, null=True)
    
    class Meta:
        verbose_name = "Data Partai"
        verbose_name_plural = "Data Partai"
        ordering = ['no_urut']
    
    def __str__(self):
        return f"{self.no_urut}. {self.nama_partai}"


class PaslonPilpres(models.Model):
    no_urut = models.IntegerField(unique=True, verbose_name="Nomor Urut")
    nama_capres = models.CharField(max_length=200, verbose_name="Nama Calon Presiden")
    nama_cawapres = models.CharField(max_length=200, verbose_name="Nama Calon Wakil Presiden")
    koalisi = models.ManyToManyField(Partai, verbose_name="Gabungan Partai Politik Pengusul", blank=True)
    foto_paslon = models.ImageField(upload_to=paslon_photo_path, verbose_name="Foto Paslon", blank=True, null=True)
    
    class Meta:
        verbose_name = "Paslon Pilpres"
        verbose_name_plural = "Data Paslon Pilpres"
        ordering = ['no_urut']
    
    def __str__(self):
        return f"{self.no_urut}. {self.nama_capres} - {self.nama_cawapres}"
    
    def get_koalisi_display(self):
        """Return comma-separated list of supporting parties"""
        return ", ".join([partai.nama_partai for partai in self.koalisi.all()])


# Signal untuk auto-delete file saat model dihapus
@receiver(post_delete, sender=Partai)
def delete_partai_logo(sender, instance, **kwargs):
    """Delete logo file when Partai is deleted"""
    if instance.logo:
        if os.path.isfile(instance.logo.path):
            os.remove(instance.logo.path)

@receiver(post_delete, sender=PaslonPilpres)
def delete_paslon_photo(sender, instance, **kwargs):
    """Delete photo file when PaslonPilpres is deleted"""
    if instance.foto_paslon:
        if os.path.isfile(instance.foto_paslon.path):
            os.remove(instance.foto_paslon.path)

# Signal untuk auto-delete file lama saat file diganti
@receiver(pre_save, sender=Partai)
def delete_old_partai_logo(sender, instance, **kwargs):
    """Delete old logo file when logo is replaced"""
    if not instance.pk:
        return False
    
    try:
        old_file = Partai.objects.get(pk=instance.pk).logo
    except Partai.DoesNotExist:
        return False
    
    new_file = instance.logo
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)

@receiver(pre_save, sender=PaslonPilpres)
def delete_old_paslon_photo(sender, instance, **kwargs):
    """Delete old photo file when photo is replaced"""
    if not instance.pk:
        return False
    
    try:
        old_file = PaslonPilpres.objects.get(pk=instance.pk).foto_paslon
    except PaslonPilpres.DoesNotExist:
        return False
    
    new_file = instance.foto_paslon
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)

# ============================================
# PILKADA MODELS
# ============================================

class KabupatenKota(models.Model):
    """Data Master Kabupaten/Kota atau Daerah"""
    nama = models.CharField(max_length=100, verbose_name="Nama Daerah", unique=True)
    
    class Meta:
        verbose_name = "Kabupaten/Kota"
        verbose_name_plural = "Data Kokab"
        ordering = ['nama']
    
    def __str__(self):
        return self.nama

class Kecamatan(models.Model):
    """Data Master Kecamatan relasi ke KabupatenKota"""
    kabupaten_kota = models.ForeignKey(
        KabupatenKota,
        on_delete=models.CASCADE,
        verbose_name="Kabupaten/Kota",
        related_name='kecamatan_set'
    )
    nama = models.CharField(max_length=100, verbose_name="Nama Kecamatan")

    class Meta:
        verbose_name = "Kecamatan"
        verbose_name_plural = "Data Kecamatan"
        ordering = ['kabupaten_kota', 'nama']
        unique_together = [['kabupaten_kota', 'nama']]

    def __str__(self):
        return self.nama


class KelurahanDesa(models.Model):
    """Data Master Kelurahan/Desa relasi ke Kabupaten dan Kecamatan"""
    kabupaten = models.ForeignKey(
        KabupatenKota,
        on_delete=models.CASCADE,
        verbose_name="Kabupaten/Kota"
    )
    kecamatan = models.ForeignKey(
        Kecamatan,
        on_delete=models.CASCADE,
        verbose_name="Kecamatan"
    )
    desa_kelurahan = models.CharField(max_length=150, verbose_name="Desa/Kelurahan")

    class Meta:
        verbose_name = "Kelurahan/Desa"
        verbose_name_plural = "Data DesKel"
        ordering = ['kabupaten', 'kecamatan', 'desa_kelurahan']
        unique_together = [['kabupaten', 'kecamatan', 'desa_kelurahan']]

    def __str__(self):
        return self.desa_kelurahan


class RekapTPSDPT(models.Model):
    """Informasi Jumlah TPS dan DPT per Desa (Terpisah Pemilu & Pilkada)"""
    desa = models.OneToOneField(
        KelurahanDesa, 
        on_delete=models.CASCADE, 
        related_name='rekap_tps_dpt',
        verbose_name="Desa/Kelurahan"
    )
    
    # Data Pemilu 2024
    tps_pemilu = models.PositiveIntegerField(default=0, verbose_name="Jumlah TPS Pemilu")
    dpt_pemilu = models.PositiveIntegerField(default=0, verbose_name="Jumlah DPT Pemilu")

    class Meta:
        verbose_name = "Data TPS & DPT"
        verbose_name_plural = "Data TPS & DPT"

    def __str__(self):
        return f"TPS/DPT - {self.desa}"


class DapilRI(models.Model):
    """Data Master Dapil RI - Cakupan wilayah Kabupaten/Kota"""
    nama = models.CharField(max_length=100, verbose_name="Nama Dapil RI", unique=True)
    alokasi_kursi = models.PositiveIntegerField(verbose_name="Alokasi Kursi")
    wilayah = models.ManyToManyField(
        KabupatenKota, 
        related_name='dapil_ri_set', 
        verbose_name="Wilayah Cakupan (Kab/Kota)",
        help_text="Pilih satu atau lebih Kabupaten/Kota yang masuk ke Dapil ini"
    )

    class Meta:
        verbose_name = "Dapil RI"
        verbose_name_plural = "Data Dapil RI"
        ordering = ['nama']

    def __str__(self):
        return self.nama


class DapilProvinsi(models.Model):
    """Data Master Dapil Provinsi - Cakupan wilayah Kabupaten/Kota"""
    nama = models.CharField(max_length=100, verbose_name="Nama Dapil Provinsi", unique=True)
    alokasi_kursi = models.PositiveIntegerField(verbose_name="Alokasi Kursi")
    wilayah = models.ManyToManyField(
        KabupatenKota, 
        related_name='dapil_prov_set', 
        verbose_name="Wilayah Cakupan (Kab/Kota)",
        help_text="Pilih satu atau lebih Kabupaten/Kota yang masuk ke Dapil ini"
    )

    class Meta:
        verbose_name = "Dapil Provinsi"
        verbose_name_plural = "Data Dapil Provinsi"
        ordering = ['nama']

    def __str__(self):
        return self.nama


class DapilKabKota(models.Model):
    """Data Master Dapil Kab/Kota - Cakupan wilayah bisa Kecamatan utuh atau Kelurahan/Desa eceran"""
    kabupaten = models.ForeignKey(
        KabupatenKota, 
        on_delete=models.CASCADE, 
        verbose_name="Kabupaten/Kota"
    )
    nama = models.CharField(max_length=100, verbose_name="Nama Dapil Kab/Kota")
    alokasi_kursi = models.PositiveIntegerField(verbose_name="Alokasi Kursi")
    
    # Hybrid Coverage
    wilayah_kecamatan = models.ManyToManyField(
        Kecamatan, 
        blank=True, 
        verbose_name="Kecamatan Utuh",
        help_text="Pilih Kecamatan yang masuk secara keseluruhan ke Dapil ini"
    )
    wilayah_desa = models.ManyToManyField(
        KelurahanDesa, 
        blank=True, 
        verbose_name="Desa/Kelurahan Eceran",
        help_text="Pilih Desa/Kelurahan tertentu (untuk Kecamatan yang terbagi ke Dapil berbeda)"
    )

    class Meta:
        verbose_name = "Dapil Kab/Kota"
        verbose_name_plural = "Data Dapil Kokab"
        ordering = ['kabupaten', 'nama']
        unique_together = [['kabupaten', 'nama']]

    def __str__(self):
        return self.nama

def pilkada_photo_path(instance, filename):
    """Generate unique filename for pilkada photo"""
    ext = filename.split('.')[-1]
    wilayah_name = instance.kabupaten_kota.nama if instance.kabupaten_kota else "JAWA_BARAT"
    wilayah_slug = wilayah_name.replace(' ', '_')
    filename = f"pilkada_{wilayah_slug}_{instance.no_urut}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('pilkada_photos', filename)


class PaslonPilkada(models.Model):
    """Model universal untuk Pasangan Calon PILKADA"""
    JENIS_PILKADA_CHOICES = [
        ('PROV', 'Provinsi (Pilgub)'),
        ('KOKAB', 'Kabupaten/Kota (Pilbup/Pilwalkot)'),
    ]
    
    jenis_pilkada = models.CharField(
        max_length=10, 
        choices=JENIS_PILKADA_CHOICES, 
        default='KOKAB',
        verbose_name="Jenis Pilkada"
    )
    kabupaten_kota = models.ForeignKey(
        'KabupatenKota', 
        on_delete=models.CASCADE, 
        verbose_name="Kabupaten/Kota", 
        related_name='paslon_set',
        null=True, blank=True,
        help_text="Pilih daerah jika Jenis Pilkada adalah Kabupaten/Kota. Kosongkan untuk tingkat Provinsi."
    )
    no_urut = models.IntegerField(verbose_name="Nomor Urut")
    nama_cakada = models.CharField(max_length=200, verbose_name="Nama Calon Kepala Daerah")
    nama_cawakada = models.CharField(max_length=200, verbose_name="Nama Calon Wakil Kepala Daerah")
    koalisi = models.ManyToManyField(Partai, verbose_name="Gabungan Partai Politik Pengusul", blank=True, related_name='paslon_pilkada_set')
    foto_paslon = models.ImageField(upload_to=pilkada_photo_path, verbose_name="Foto Paslon", blank=True, null=True)
    
    class Meta:
        verbose_name = "Paslon Pilkada"
        verbose_name_plural = "Data Paslon Pilkada"
        ordering = ['jenis_pilkada', 'kabupaten_kota', 'no_urut']
        unique_together = [['jenis_pilkada', 'kabupaten_kota', 'no_urut']]
    
    def __str__(self):
        if self.jenis_pilkada == 'PROV':
            wilayah = "JAWA BARAT"
        else:
            wilayah = str(self.kabupaten_kota) if self.kabupaten_kota else "Sudah Dihapus"
        return f"{wilayah} - {self.no_urut}. {self.nama_cakada} - {self.nama_cawakada}"
    
    def get_koalisi_display(self):
        """Return comma-separated list of supporting parties"""
        return ", ".join([partai.nama_partai for partai in self.koalisi.all()])


# Signals untuk auto-delete file PILKADA
@receiver(post_delete, sender=PaslonPilkada)
def delete_pilkada_photo(sender, instance, **kwargs):
    """Delete photo file when PaslonPilkada is deleted"""
    if instance.foto_paslon:
        if os.path.isfile(instance.foto_paslon.path):
            os.remove(instance.foto_paslon.path)

@receiver(pre_save, sender=PaslonPilkada)
def delete_old_pilkada_photo(sender, instance, **kwargs):
    """Delete old photo file when photo is replaced"""
    if not instance.pk:
        return False
    
    try:
        old_file = PaslonPilkada.objects.get(pk=instance.pk).foto_paslon
    except PaslonPilkada.DoesNotExist:
        return False
    
    new_file = instance.foto_paslon
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


def caleg_ri_photo_path(instance, filename):
    """Generate unique filename for caleg RI photo"""
    ext = filename.split('.')[-1]
    # Sanitize names for filename
    dapil_slug = instance.dapil.nama.replace(' ', '_')
    partai_slug = instance.partai.nama_partai.replace(' ', '_')
    filename = f"caleg_ri_{dapil_slug}_{partai_slug}_{instance.nomor_urut}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('caleg_ri_photos', filename)

class CalegRI(models.Model):
    """Data Caleg DPR RI"""
    partai = models.ForeignKey(Partai, on_delete=models.CASCADE, verbose_name="Partai")
    dapil = models.ForeignKey(DapilRI, on_delete=models.CASCADE, verbose_name="Dapil RI")
    nomor_urut = models.PositiveIntegerField(verbose_name="Nomor Urut")
    nama = models.CharField(max_length=150, verbose_name="Nama Lengkap")
    JENIS_KELAMIN_CHOICES = [
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    ]
    jenis_kelamin = models.CharField(max_length=1, choices=JENIS_KELAMIN_CHOICES, verbose_name="Jenis Kelamin")
    foto = models.ImageField(upload_to=caleg_ri_photo_path, blank=True, null=True, verbose_name="Foto Caleg")

    class Meta:
        verbose_name = "Caleg DPR RI"
        verbose_name_plural = "Data Caleg RI"
        ordering = ['dapil', 'partai', 'nomor_urut']
        unique_together = [['dapil', 'partai', 'nomor_urut']]

    def __str__(self):
        return f"{self.nomor_urut}. {self.nama} ({self.partai.nama_partai})"

# Signals untuk auto-delete file Caleg RI
@receiver(post_delete, sender=CalegRI)
def delete_caleg_ri_photo(sender, instance, **kwargs):
    """Delete photo file when CalegRI is deleted"""
    if instance.foto:
        if os.path.isfile(instance.foto.path):
            os.remove(instance.foto.path)

@receiver(pre_save, sender=CalegRI)
def delete_old_caleg_ri_photo(sender, instance, **kwargs):
    """Delete old photo file when photo is replaced"""
    if not instance.pk:
        return False
    
    try:
        old_file = CalegRI.objects.get(pk=instance.pk).foto
    except CalegRI.DoesNotExist:
        return False
    
    new_file = instance.foto
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


def caleg_prov_photo_path(instance, filename):
    """Generate unique filename for caleg Provinsi photo"""
    ext = filename.split('.')[-1]
    dapil_slug = instance.dapil.nama.replace(' ', '_')
    partai_slug = instance.partai.nama_partai.replace(' ', '_')
    filename = f"caleg_prov_{dapil_slug}_{partai_slug}_{instance.nomor_urut}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('caleg_prov_photos', filename)

class CalegProvinsi(models.Model):
    """Data Caleg DPRD Provinsi"""
    partai = models.ForeignKey(Partai, on_delete=models.CASCADE, verbose_name="Partai")
    dapil = models.ForeignKey(DapilProvinsi, on_delete=models.CASCADE, verbose_name="Dapil Provinsi")
    nomor_urut = models.PositiveIntegerField(verbose_name="Nomor Urut")
    nama = models.CharField(max_length=150, verbose_name="Nama Lengkap")
    JENIS_KELAMIN_CHOICES = [
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    ]
    jenis_kelamin = models.CharField(max_length=1, choices=JENIS_KELAMIN_CHOICES, verbose_name="Jenis Kelamin")
    foto = models.ImageField(upload_to=caleg_prov_photo_path, blank=True, null=True, verbose_name="Foto Caleg")

    class Meta:
        verbose_name = "Caleg DPRD Provinsi"
        verbose_name_plural = "Data Caleg Provinsi"
        ordering = ['dapil', 'partai', 'nomor_urut']
        unique_together = [['dapil', 'partai', 'nomor_urut']]

    def __str__(self):
        return f"{self.nomor_urut}. {self.nama} ({self.partai.nama_partai})"

# Signals untuk auto-delete file Caleg Provinsi
@receiver(post_delete, sender=CalegProvinsi)
def delete_caleg_prov_photo(sender, instance, **kwargs):
    """Delete photo file when CalegProvinsi is deleted"""
    if instance.foto:
        if os.path.isfile(instance.foto.path):
            os.remove(instance.foto.path)

@receiver(pre_save, sender=CalegProvinsi)
def delete_old_caleg_prov_photo(sender, instance, **kwargs):
    """Delete old photo file when photo is replaced"""
    if not instance.pk:
        return False
    
    try:
        old_file = CalegProvinsi.objects.get(pk=instance.pk).foto
    except CalegProvinsi.DoesNotExist:
        return False
    
    new_file = instance.foto
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


def caleg_kabkota_photo_path(instance, filename):
    """Generate unique filename for caleg Kab/Kota photo"""
    ext = filename.split('.')[-1]
    dapil_slug = instance.dapil.nama.replace(' ', '_')
    partai_slug = instance.partai.nama_partai.replace(' ', '_')
    filename = f"caleg_kabkota_{dapil_slug}_{partai_slug}_{instance.nomor_urut}_{uuid.uuid4().hex[:8]}.{ext}"
    return os.path.join('caleg_kabkota_photos', filename)

class CalegKabKota(models.Model):
    """Data Caleg DPRD Kabupaten/Kota"""
    partai = models.ForeignKey(Partai, on_delete=models.CASCADE, verbose_name="Partai")
    dapil = models.ForeignKey(DapilKabKota, on_delete=models.CASCADE, verbose_name="Dapil Kab/Kota")
    nomor_urut = models.PositiveIntegerField(verbose_name="Nomor Urut")
    nama = models.CharField(max_length=150, verbose_name="Nama Lengkap")
    JENIS_KELAMIN_CHOICES = [
        ('L', 'Laki-laki'),
        ('P', 'Perempuan'),
    ]
    jenis_kelamin = models.CharField(max_length=1, choices=JENIS_KELAMIN_CHOICES, verbose_name="Jenis Kelamin")
    foto = models.ImageField(upload_to=caleg_kabkota_photo_path, blank=True, null=True, verbose_name="Foto Caleg")

    class Meta:
        verbose_name = "Caleg DPRD Kab/Kota"
        verbose_name_plural = "Data Caleg Kokab"
        ordering = ['dapil', 'partai', 'nomor_urut']
        unique_together = [['dapil', 'partai', 'nomor_urut']]

    def __str__(self):
        return f"{self.nomor_urut}. {self.nama} ({self.partai.nama_partai})"

# Signals untuk auto-delete file Caleg Kab/Kota
@receiver(post_delete, sender=CalegKabKota)
def delete_caleg_kabkota_photo(sender, instance, **kwargs):
    """Delete photo file when CalegKabKota is deleted"""
    if instance.foto:
        if os.path.isfile(instance.foto.path):
            os.remove(instance.foto.path)

@receiver(pre_save, sender=CalegKabKota)
def delete_old_caleg_kabkota_photo(sender, instance, **kwargs):
    """Delete old photo file when photo is replaced"""
    if not instance.pk:
        return False
    
    try:
        old_file = CalegKabKota.objects.get(pk=instance.pk).foto
    except CalegKabKota.DoesNotExist:
        return False
    
    new_file = instance.foto
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)


# ============================================
# INPUT PEROLEHAN SUARA (PILPRES)
# ============================================

class SuaraPilpres(models.Model):
    """
    Model tunggal untuk menyimpan seluruh perolehan suara di satu Desa dalam satu record.
    """
    desa = models.OneToOneField(KelurahanDesa, on_delete=models.CASCADE, verbose_name="Desa/Kelurahan", related_name="rekap_suara_pilpres")
    
    # Perolehan Suara Sah (Flat fields untuk kemudahan input satu baris)
    suara_paslon_1 = models.PositiveIntegerField(default=0, verbose_name="Suara Paslon 01")
    suara_paslon_2 = models.PositiveIntegerField(default=0, verbose_name="Suara Paslon 02")
    suara_paslon_3 = models.PositiveIntegerField(default=0, verbose_name="Suara Paslon 03")
    
    # Suara Tidak Sah
    suara_tidak_sah = models.PositiveIntegerField(default=0, verbose_name="Jumlah Suara Tidak Sah")

    class Meta:
        verbose_name = "Perolehan Suara Pilpres"
        verbose_name_plural = "Data Perolehan Suara Pilpres"

    @property
    def total_suara_sah(self):
        return self.suara_paslon_1 + self.suara_paslon_2 + self.suara_paslon_3

    @property
    def total_suara_masuk(self):
        return self.total_suara_sah + self.suara_tidak_sah

    def __str__(self):
        return f"Rekap Pilpres - {self.desa}"


# ============================================
# REKAPITULASI TINGKAT KECAMATAN
# ============================================

class RekapTPSDPTKecamatan(models.Model):
    """Informasi Jumlah TPS dan DPT per Kecamatan (Data Resmi Kecamatan)"""
    kecamatan = models.OneToOneField(
        Kecamatan, 
        on_delete=models.CASCADE, 
        related_name='rekap_tps_dpt_kecamatan',
        verbose_name="Kecamatan"
    )
    tps_pemilu = models.PositiveIntegerField(default=0, verbose_name="Jumlah TPS Pemilu (Kecamatan)")
    dpt_pemilu = models.PositiveIntegerField(default=0, verbose_name="Jumlah DPT Pemilu (Kecamatan)")

    class Meta:
        verbose_name = "Rekap TPS & DPT Kecamatan"
        verbose_name_plural = "Rekap TPS & DPT Kecamatan"

    def __str__(self):
        return f"TPS/DPT Kec. {self.kecamatan.nama}"


class SuaraPilpresKecamatan(models.Model):
    """Rekapitulasi Suara Pilpres di tingkat Kecamatan (Data Resmi Kecamatan)"""
    kecamatan = models.OneToOneField(
        Kecamatan, 
        on_delete=models.CASCADE, 
        related_name='rekap_suara_pilpres_kecamatan',
        verbose_name="Kecamatan"
    )
    suara_paslon_1 = models.PositiveIntegerField(default=0, verbose_name="Suara Paslon 01")
    suara_paslon_2 = models.PositiveIntegerField(default=0, verbose_name="Suara Paslon 02")
    suara_paslon_3 = models.PositiveIntegerField(default=0, verbose_name="Suara Paslon 03")
    suara_tidak_sah = models.PositiveIntegerField(default=0, verbose_name="Jumlah Suara Tidak Sah")

    class Meta:
        verbose_name = "Rekap Suara Pilpres Kecamatan"
        verbose_name_plural = "Rekap Suara Pilpres Kecamatan"

    @property
    def total_suara_sah(self):
        return self.suara_paslon_1 + self.suara_paslon_2 + self.suara_paslon_3

    @property
    def total_suara_masuk(self):
        return self.total_suara_sah + self.suara_tidak_sah

    def __str__(self):
        return f"Suara Pilpres Kec. {self.kecamatan.nama}"
