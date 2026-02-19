from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
import json

from .models import GeoKokab, GeoKecamatan, GeoDesKel

# =========================================================================
# BAGIAN 5: GEOSPATIAL ADMIN (PETA DIGITAL)
# =========================================================================
class GeoAdminMixin:
    """Mixin untuk fungsi bersama antara data geospatial (Kokab, Kec, Deskel)"""
    def preview_peta(self, obj):
        if not obj or not obj.vektor_wilayah:
            return "Belum ada data vektor untuk ditampilkan."
        
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
                            var colorInput = document.getElementById('id_warna_area');
                            var defaultColor = "{2}";
                            
                            mapLayer = L.geoJSON(geoData, {{
                                style: function(feature) {{
                                    var currentColor = colorInput ? colorInput.value : defaultColor;
                                    return {{
                                        color: currentColor,
                                        weight: 3,
                                        fillOpacity: 0.4
                                    }};
                                }}
                            }}).addTo(map);
                            
                            // Auto Zoom ke tengah wilayah
                            if (mapLayer.getLayers().length > 0) {{
                                map.fitBounds(mapLayer.getBounds(), {{ padding: [30, 30] }});
                            }}

                            // LIVE COLOR UPDATE (Hanya jika input ada/editable)
                            if (colorInput) {{
                                colorInput.addEventListener('input', function(e) {{
                                    if (mapLayer) {{
                                        mapLayer.setStyle({{ color: e.target.value }});
                                    }};
                                }});
                            }}

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
    list_display = ['kokab', 'warna_area', 'last_update']
    search_fields = ['kokab__nama']
    readonly_fields = ['preview_peta']
    
    fieldsets = (
        ("Informasi Wilayah", {
            "fields": ("kokab", "warna_area", "preview_peta")
        }),
        ("Data Vektor (GeoJSON)", {
            "classes": ("collapse",),
            "fields": ("vektor_wilayah",),
            "description": "Data poligon wilayah dalam format GeoJSON string. Biarkan tertutup jika tidak diedit."
        }),
    )

@admin.register(GeoKecamatan)
class GeoKecamatanAdmin(GeoAdminMixin, admin.ModelAdmin):
    list_display = ['kecamatan', 'get_kab_nama', 'warna_area']
    search_fields = ['kecamatan__nama', 'kecamatan__kabupaten_kota__nama']
    list_filter = ['kecamatan__kabupaten_kota']
    readonly_fields = ['preview_peta']
    autocomplete_fields = ['kecamatan']

    fieldsets = (
        ("Informasi Wilayah", {
            "fields": ("kecamatan", "warna_area", "preview_peta")
        }),
        ("Data Vektor (GeoJSON)", {
            "classes": ("collapse",),
            "fields": ("vektor_wilayah",),
        }),
    )

@admin.register(GeoDesKel)
class GeoDesKelAdmin(GeoAdminMixin, admin.ModelAdmin):
    list_display = ['deskel', 'get_kec_nama', 'get_kab_nama', 'warna_area']
    search_fields = ['deskel__desa_kelurahan', 'deskel__kecamatan__nama', 'deskel__kecamatan__kabupaten_kota__nama']
    list_filter = ['deskel__kecamatan__kabupaten_kota', 'deskel__kecamatan']
    readonly_fields = ['preview_peta']
    autocomplete_fields = ['deskel']

    fieldsets = (
        ("Informasi Wilayah", {
            "fields": ("deskel", "warna_area", "preview_peta")
        }),
        ("Data Vektor (GeoJSON)", {
            "classes": ("collapse",),
            "fields": ("vektor_wilayah",),
        }),
    )
