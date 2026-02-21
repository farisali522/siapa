from django.db import models
from django.db.models import Sum, F, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from core.models import KabupatenKota, DapilRI

class RekapSuaraQuerySet(models.QuerySet):
    def with_totals(self):
        """Menggunakan Subquery agar hitungan Sah dan Total tidak meledak/ganda (Fan-out fix)."""
        from .models import DetailSuaraCaleg, SuaraPartai
        return self.annotate(
            t_caleg=Coalesce(Subquery(
                DetailSuaraCaleg.objects.filter(rekap_suara=OuterRef('pk')).values('rekap_suara').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0),
            t_partai=Coalesce(Subquery(
                SuaraPartai.objects.filter(rekap_suara=OuterRef('pk')).values('rekap_suara').annotate(t=Sum('jumlah_suara')).values('t'),
                output_field=IntegerField()
            ), 0)
        ).annotate(
            t_sah=F('t_caleg') + F('t_partai'),
            t_total=F('t_caleg') + F('t_partai') + F('suara_tidak_sah')
        )

class Caleg(models.Model):
    no_urut = models.IntegerField(db_index=True, verbose_name="No. Urut")
    nama = models.CharField(max_length=255, db_index=True, verbose_name="Nama Lengkap")
    partai = models.ForeignKey('core.Partai', on_delete=models.CASCADE, related_name='caleg_ri_set')
    daerah_pemilihan = models.ForeignKey('core.DapilRI', on_delete=models.CASCADE, related_name='caleg_ri_set')
    foto = models.ImageField(upload_to='caleg_ri/', null=True, blank=True)
    jenis_kelamin = models.CharField(max_length=1, choices=[('L', 'Laki-laki'), ('P', 'Perempuan')], default='L')

    class Meta:
        verbose_name = "Data Caleg RI"
        verbose_name_plural = "Data Caleg RI"
        unique_together = ('no_urut', 'partai', 'daerah_pemilihan')
        ordering = ['daerah_pemilihan', 'partai__no_urut', 'no_urut']

    def __str__(self):
        return f"[{self.partai.nama}] {self.no_urut}. {self.nama}"

class RekapSuara(models.Model):
    kecamatan = models.OneToOneField('core.Kecamatan', on_delete=models.CASCADE, related_name='hasil_pileg_ri')
    suara_tidak_sah = models.IntegerField(default=0)
    objects = RekapSuaraQuerySet.as_manager()

    class Meta:
        verbose_name = "Rekap Suara RI"
        verbose_name_plural = "Rekap Suara RI"

    def __str__(self):
        return f"Rekap {self.kecamatan.nama}"

class DetailSuaraCaleg(models.Model):
    rekap_suara = models.ForeignKey(RekapSuara, on_delete=models.CASCADE, related_name='rincian_suara')
    caleg = models.ForeignKey(Caleg, on_delete=models.CASCADE, related_name='data_suara_kecamatan')
    jumlah_suara = models.IntegerField(default=0)

    class Meta:
        unique_together = ('rekap_suara', 'caleg')

class SuaraPartai(models.Model):
    rekap_suara = models.ForeignKey(RekapSuara, on_delete=models.CASCADE, related_name='rincian_suara_partai')
    partai = models.ForeignKey('core.Partai', on_delete=models.CASCADE, related_name='suara_partai_ri_set')
    jumlah_suara = models.IntegerField(default=0)

    class Meta:
        unique_together = ('rekap_suara', 'partai')

class KabupatenPilegRI(KabupatenKota):
    class Meta:
        proxy = True
        verbose_name = "Rekap Kabupaten RI"
        verbose_name_plural = "Rekap Kabupaten RI"

class DapilPilegRI(DapilRI):
    class Meta:
        proxy = True
        verbose_name = "Rekap Dapil RI"
        verbose_name_plural = "Rekap Dapil RI"