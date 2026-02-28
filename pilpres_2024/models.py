from django.db import models
from core.models import Partai, KabupatenKota

# ==============================================================================
# MODEL PASLON PILPRES 2024
# ==============================================================================

class PaslonPilpresQuerySet(models.QuerySet):
    def with_totals(self):
        from django.db.models import Sum, Subquery, IntegerField
        from django.db.models.functions import Coalesce
        from .models import DetailSuaraPaslon
        
        qs = self.prefetch_related('koalisi').annotate(total_suara=Sum('data_suara_kecamatan__jumlah_suara'))
        qs = qs.annotate(
            total_sah_all=Coalesce(Subquery(
                DetailSuaraPaslon.objects.values('paslon__id').annotate(
                    all_t=Sum('jumlah_suara')
                ).filter(paslon__id__isnull=False).values('all_t')[:1]
            ), 0)
        )
        return qs

class PaslonPilpres(models.Model):
    objects = PaslonPilpresQuerySet.as_manager()
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

class RekapSuaraPilpresQuerySet(models.QuerySet):
    def with_totals(self):
        from django.db.models import Sum, F, Q
        return self.select_related(
            'kecamatan', 'kecamatan__kabupaten_kota', 'kecamatan__tpsdpt_pemilu'
        ).annotate(
            total_sah_db=Sum('rincian_suara__jumlah_suara'),
            total_masuk_db=Sum('rincian_suara__jumlah_suara') + F('suara_tidak_sah'),
            s1=Sum('rincian_suara__jumlah_suara', filter=Q(rincian_suara__paslon__no_urut=1)),
            s2=Sum('rincian_suara__jumlah_suara', filter=Q(rincian_suara__paslon__no_urut=2)),
            s3=Sum('rincian_suara__jumlah_suara', filter=Q(rincian_suara__paslon__no_urut=3)),
        )

class RekapSuaraPilpres(models.Model):
    objects = RekapSuaraPilpresQuerySet.as_manager()
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


class KabupatenPilpresQuerySet(models.QuerySet):
    def with_totals(self):
        from django.db.models import Sum, OuterRef, Subquery, IntegerField, F
        from django.db.models.functions import Coalesce
        from .models import DetailSuaraPaslon, RekapSuaraPilpres
        
        rekap_qs = RekapSuaraPilpres.objects.filter(kecamatan__kabupaten_kota=OuterRef('pk'))
        
        qs = self.annotate(
            tps_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_tps'), 0),
            dpt_total=Coalesce(Sum('kecamatan_set__tpsdpt_pemilu__jumlah_dpt'), 0),
            s1_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), paslon__no_urut=1
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(total=Sum('jumlah_suara')).values('total'),
                output_field=IntegerField()
            ), 0),
            s2_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), paslon__no_urut=2
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(total=Sum('jumlah_suara')).values('total'),
                output_field=IntegerField()
            ), 0),
            s3_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk'), paslon__no_urut=3
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(total=Sum('jumlah_suara')).values('total'),
                output_field=IntegerField()
            ), 0),
            sah_total=Coalesce(Subquery(
                DetailSuaraPaslon.objects.filter(
                    rekap_suara__kecamatan__kabupaten_kota=OuterRef('pk')
                ).values('rekap_suara__kecamatan__kabupaten_kota').annotate(total=Sum('jumlah_suara')).values('total'),
                output_field=IntegerField()
            ), 0),
            tidak_sah_total=Coalesce(Subquery(
                rekap_qs.values('kecamatan__kabupaten_kota').annotate(total=Sum('suara_tidak_sah')).values('total'),
                output_field=IntegerField()
            ), 0)
        )
        return qs.annotate(total_masuk_db=F('sah_total') + F('tidak_sah_total'))

class KabupatenPilpres(KabupatenKota):
    objects = KabupatenPilpresQuerySet.as_manager()
    """Proxy model untuk menampilkan data Pilpres pada tingkat Kabupaten/Kota.

    Proxy model tidak membuat tabel baru sehingga tidak memerlukan migrasi.
    Admin akan menghitung agregat dari `RekapSuaraPilpres` saat ditampilkan.
    """
    class Meta:
        proxy = True
        verbose_name = "Rekap Kabupaten Pilpres"
        verbose_name_plural = "Rekap Kabupaten Pilpres"
