document.addEventListener('DOMContentLoaded', function() {
    const jenisField = document.querySelector('#id_jenis_pilkada');
    const wilayahField = document.querySelector('#id_kabupaten_kota');
    const wilayahRow = document.querySelector('.field-kabupaten_kota');

    if (jenisField && wilayahRow) {
        function toggleWilayah() {
            if (jenisField.value === 'PROV') {
                wilayahRow.style.display = 'none';
            } else {
                wilayahRow.style.display = 'block';
            }
        }

        function refreshForm() {
            // Only auto-reload if we are on an "ADD" page (no PK in URL)
            const path = window.location.pathname;
            if (path.includes('/add/')) {
                const jenis = jenisField.value;
                const wilayah = wilayahField ? wilayahField.value : '';
                
                let url = new URL(window.location.href);
                url.searchParams.set('jenis_pilkada', jenis);
                if (wilayah) {
                    url.searchParams.set('kabupaten_kota', wilayah);
                } else {
                    url.searchParams.delete('kabupaten_kota');
                }
                
                // Don't reload if values haven't actually changed from URL
                if (window.location.search !== url.search) {
                    window.location.href = url.href;
                }
            }
        }

        // Initial check
        toggleWilayah();

        // Listen for changes
        jenisField.addEventListener('change', function() {
            toggleWilayah();
            refreshForm();
        });

        if (wilayahField) {
            wilayahField.addEventListener('change', refreshForm);
        }
    }
});
