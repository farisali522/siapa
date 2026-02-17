(function($) {
    'use strict';
    const $jq = (window.django && window.django.jQuery) ? window.django.jQuery : (window.jQuery || $);

    $jq(document).ready(function() {
        console.log("Suara Pilpres Calculator Loaded");

        function calculateResults(row) {
            // Jika row tidak diberikan, asumsikan form utama
            const prefix = row ? row.find('input[id$="-suara_paslon_1"]').attr('id').replace('suara_paslon_1', '') : 'id_';
            
            const p1 = parseInt($jq('#' + prefix + 'suara_paslon_1').val()) || 0;
            const p2 = parseInt($jq('#' + prefix + 'suara_paslon_2').val()) || 0;
            const p3 = parseInt($jq('#' + prefix + 'suara_paslon_3').val()) || 0;
            const tdkSah = parseInt($jq('#' + prefix + 'suara_tidak_sah').val()) || 0;

            const sah = p1 + p2 + p3;
            const total = sah + tdkSah;
            
            // Update label/info di Django Admin secara real-time
            const $sahDisplay = row.find('.field-total_suara_sah_display .readonly');
            const $totalDisplay = row.find('.field-total_suara_masuk_display .readonly');
            
            if ($sahDisplay.length) $sahDisplay.text(sah.toLocaleString());
            if ($totalDisplay.length) $totalDisplay.text(total.toLocaleString());

            console.log(`Calculate for ${prefix}: Sah=${sah}, Total=${total}`);
        }

        // Listener untuk standalone
        $jq(document).on('input', 'input[id^="id_suara_paslon_"], #id_suara_tidak_sah', function() {
            calculateResults();
        });

        // Listener untuk inline (biasanya id-nya diawali dengan prefix set)
        $jq(document).on('input', 'input[id*="-suara_paslon_"], input[id*="-suara_tidak_sah"]', function() {
            const row = $jq(this).closest('.stacked-inline, .tabular-inline, tr');
            if (row.length) {
                calculateResults(row);
            }
        });
    });
})(window.jQuery);
