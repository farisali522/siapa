(function($) {
    'use strict';
    // Gunakan django.jQuery jika ada, jika tidak fallback ke jQuery standar
    const $jq = (window.django && window.django.jQuery) ? window.django.jQuery : $;
    
    $jq(function() {
        const kabField = $jq('#id_kabupaten');
        const kecField = $jq('#id_kecamatan');
        const desaField = $jq('#id_desa');

        if (kabField.length && kecField.length && desaField.length) {
            // --- 1. HANDLING KABUPATEN CHANGE ---
            kabField.on('change', function() {
                const kabId = $jq(this).val();
                
                // Reset fields below
                kecField.html('<option value="">---------</option>');
                desaField.html('<option value="">---------</option>');

                if (!kabId) return;

                // Fetch Kecamatan
                $jq.getJSON(`/get_kecamatan/?kabupaten_id=${kabId}`, function(data) {
                    $jq.each(data, function(index, item) {
                        kecField.append($jq('<option>', {
                            value: item.id,
                            text: item.nama
                        }));
                    });
                });
            });

            // --- 2. HANDLING KECAMATAN CHANGE ---
            kecField.on('change', function() {
                const kecId = $jq(this).val();

                // Reset desa below
                desaField.html('<option value="">---------</option>');

                if (!kecId) return;

                // Fetch Desa
                $jq.getJSON(`/get_desa/?kecamatan_id=${kecId}`, function(data) {
                    $jq.each(data, function(index, item) {
                        desaField.append($jq('<option>', {
                            value: item.id,
                            text: item.nama
                        }));
                    });
                });
            });
        }
    });
})(window.jQuery);
