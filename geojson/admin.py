from django.contrib import admin
from django.utils.html import mark_safe
from .models import KabupatenGeoJSON, KecamatanGeoJSON
import json

class GeoJSONMapPreviewMixin:
    """Modul Mixin untuk merender Leaflet JS di dalam form Admin Django"""
    readonly_fields = ('peta_preview',)
    
    @admin.display(description="Preview Peta Wilayah")
    def peta_preview(self, obj):
        if not obj or not obj.geojson_data:
            return mark_safe("<i>Data koordinat peta belum diunggah.</i>")
            
        data = obj.geojson_data
        if isinstance(data, str):
            data_json = data
        else:
            data_json = json.dumps(data)
            
        # Gunakan ID unik untuk menampung map Leaflet
        map_id = f"leaflet_map_{obj.pk}"
        html = f"""
        <!-- Menyisipkan dependensi pustaka Leaflet -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        
        <!-- Wadah Rendering -->
        <div id="{map_id}" style="width: 100%; height: 450px; border-radius: 8px; border: 1px solid #ccc; z-index: 1;"></div>
        
        <!-- Logic JS -->
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                var map = L.map('{map_id}', {{ zoomControl: false }}).setView([-6.9175, 107.6191], 8);
                L.control.zoom({{ position: 'topright' }}).addTo(map);
                
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19
                }}).addTo(map);
                
                var rawData = {data_json};
                
                var layer = L.geoJSON(rawData, {{
                    style: function(feature) {{
                        return {{ color: "#555555", weight: 0.8, opacity: 1.0, fillOpacity: 0.35, fillColor: "#808080" }};
                    }}
                }}).addTo(map);
                
                // Secara otomatis fokus zoom (bind) peta agar pas dengan batas ukur poligonnya
                try {{
                    map.fitBounds(layer.getBounds(), {{ padding: [20, 20] }});
                }} catch(e) {{}}
            }});
        </script>
        """
        return mark_safe(html)

from django.db import models

class HasGeoJSONFilter(admin.SimpleListFilter):
    title = 'Status GeoJSON'
    parameter_name = 'has_geojson'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Sudah Ada (✅)'),
            ('no', 'Belum Ada (✖)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(geojson_data__isnull=True).exclude(geojson_data__exact='')
        if self.value() == 'no':
            return queryset.filter(models.Q(geojson_data__isnull=True) | models.Q(geojson_data__exact=''))
        return queryset

@admin.register(KabupatenGeoJSON)
class KabupatenGeoJSONAdmin(GeoJSONMapPreviewMixin, admin.ModelAdmin):
    list_display = ('kabupaten', 'has_geojson_data')
    search_fields = ('kabupaten__nama',)
    list_filter = (HasGeoJSONFilter,)
    autocomplete_fields = ('kabupaten',)
    # Menampilkan atribut admin + map preview
    fields = ('kabupaten', 'peta_preview', 'geojson_data')
    ordering = ('kabupaten__nama',)
    list_per_page = 10

    @admin.display(description="GeoJSON Dimasukkan", boolean=True)
    def has_geojson_data(self, obj):
        return bool(obj.geojson_data)


@admin.register(KecamatanGeoJSON)
class KecamatanGeoJSONAdmin(GeoJSONMapPreviewMixin, admin.ModelAdmin):
    list_display = ('kecamatan', 'get_kabupaten', 'has_geojson_data')
    search_fields = ('kecamatan__nama', 'kecamatan__kabupaten_kota__nama')
    list_filter = ('kecamatan__kabupaten_kota', HasGeoJSONFilter)
    autocomplete_fields = ('kecamatan',)
    # Menampilkan atribut admin + map preview
    fields = ('kecamatan', 'peta_preview', 'geojson_data')
    ordering = ('kecamatan__kabupaten_kota__nama', 'kecamatan__nama')
    list_per_page = 10
    list_max_show_all = 1000

    @admin.display(description="Kabupaten/Kota", ordering="kecamatan__kabupaten_kota__nama")
    def get_kabupaten(self, obj):
        return obj.kecamatan.kabupaten_kota.nama if obj.kecamatan else "-"

    @admin.display(description="GeoJSON Dimasukkan", boolean=True)
    def has_geojson_data(self, obj):
        return bool(obj.geojson_data)

