from django.db import models
from core.models import Partai, KabupatenKota

# ==============================================================================
# MODEL PASLON PILPRES 2024
# ==============================================================================

class PaslonPilpres(models.Model):
    no_urut = models.IntegerField(unique=True, verbose_name="No. Urut", db_index=True)
    nama_capres = models.CharField(max_length=255, verbose_name="Nama Calon Presiden")
    nama_cawapres = models.CharField(max_length=255, verbose_name="Nama Calon Wakil Presiden")
    foto_paslon = models.ImageField(upload_to='paslon_pilpres/', null=True, blank=True, verbose_name="Foto Pasangan")
    warna_hex = models.CharField(max_length=7, default="#FFFFFF", verbose_name="Warna Identitas")
    
    koalisi = models.ManyToManyField(
        Partai, 
        through='KoalisiPilpres',
        related_name='paslon_pilpres_dijunjung',
        verbose_name="Partai Koalisi"
    )

    class Meta:
        verbose_name = "Paslon Pilpres 2024"
        verbose_name_plural = "Data Paslon Pilpres"
        ordering = ['no_urut']

    def __str__(self):
        return f"{self.no_urut}. {self.nama_capres} - {self.nama_cawapres}"


class KoalisiPilpres(models.Model):
    partai = models.OneToOneField(Partai, on_delete=models.CASCADE, verbose_name="Partai", related_name='koalisi_pilpres_terdaftar')
    paslon = models.ForeignKey(PaslonPilpres, on_delete=models.CASCADE, verbose_name="Dukungan Ke Paslon", related_name='daftar_koalisi')

    class Meta:
        verbose_name = "Dukungan Partai (Koalisi)"
        verbose_name_plural = "Dukungan Partai (Koalisi)"

    def __str__(self):
        return f"{self.partai.nama} -> Paslon {self.paslon.no_urut}"


# ==============================================================================
# MODEL REKAP SUARA (MASTER-DETAIL)
# ==============================================================================

class RekapSuaraPilpres(models.Model):
    """
    Model Master untuk rekapitulasi suara di tingkat Kecamatan.
    Menyimpan data agregat suara tidak sah dan terhubung ke rincian suara per Paslon.
    """
    kecamatan = models.OneToOneField(
        'core.Kecamatan', 
        on_delete=models.CASCADE,
        related_name='hasil_pilpres',
        verbose_name="Kecamatan"
    )
    suara_tidak_sah = models.IntegerField(default=0, verbose_name="Suara Tidak Sah")

    class Meta:
        verbose_name = "Rekap Suara Pilpres"
        verbose_name_plural = "Rekap Suara Pilpres"

    def __str__(self):
        return f"Rekap {self.kecamatan.nama}"

    @property
    def total_suara_sah(self):
        # Gunakan hasil perhitungan DB (annotation) jika ada, biar cepat
        if hasattr(self, 'total_sah_db'):
            return self.total_sah_db or 0
        return sum(d.jumlah_suara for d in self.rincian_suara.all())

    @property
    def total_suara_masuk(self):
        return self.total_suara_sah + self.suara_tidak_sah


class DetailSuaraPaslon(models.Model):
    """
    Model Detail untuk rincian perolehan suara setiap Paslon.
    Merupakan data anak dari RekapSuaraPilpres.
    """
    rekap_suara = models.ForeignKey(
        RekapSuaraPilpres, 
        on_delete=models.CASCADE,
        related_name='rincian_suara',
        verbose_name="Rekap Suara"
    )
    paslon = models.ForeignKey(
        PaslonPilpres, 
        on_delete=models.CASCADE,
        related_name='data_suara_kecamatan',
        verbose_name="Paslon"
    )
    jumlah_suara = models.IntegerField(default=0, verbose_name="Jumlah Suara Sah")

    class Meta:
        verbose_name = "Detail Suara Paslon"
        verbose_name_plural = "Detail Suara Paslon"
        unique_together = ('rekap_suara', 'paslon')

    def __str__(self):
        return f"{self.paslon.nama_capres}: {self.jumlah_suara}"


class KabupatenPilpres(KabupatenKota):
    """Proxy model untuk menampilkan data Pilpres pada tingkat Kabupaten/Kota.

    Proxy model tidak membuat tabel baru sehingga tidak memerlukan migrasi.
    Admin akan menghitung agregat dari `RekapSuaraPilpres` saat ditampilkan.
    """
    class Meta:
        proxy = True
        verbose_name = "Rekap Kabupaten Pilpres"
        verbose_name_plural = "Rekap Kabupaten Pilpres"
