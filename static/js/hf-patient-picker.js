/**
 * Alpine.js data factory for health-forms patient search + profile prefill.
 */
(function () {
  function hfPatientPickerFactory(config) {
    config = config || {};
    return {
      query: '',
      loading: false,
      results: [],
      searchSeq: 0,
      activeSearch: 0,
      selectedPatient: config.initialSelected || null,

      searchPatients() {
        const q = (this.query || '').trim();
        if (q.length < 2) {
          this.results = [];
          this.loading = false;
          return;
        }
        const seq = ++this.searchSeq;
        this.activeSearch = seq;
        this.loading = true;
        const url = `${config.searchUrl}?q=${encodeURIComponent(q)}`;
        fetch(url, {
          credentials: 'same-origin',
          headers: {
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then((r) => (r.ok ? r.json() : { results: [] }))
          .then((data) => {
            if (seq === this.activeSearch) {
              this.results = data.results || [];
            }
          })
          .catch(() => {
            if (seq === this.activeSearch) {
              this.results = [];
            }
          })
          .finally(() => {
            if (seq === this.activeSearch) {
              this.loading = false;
            }
          });
      },

      selectPatient(item) {
        this.selectedPatient = {
          id: String(item.id),
          name: item.name || item.text || '',
          email: item.email || '',
          patientId: item.patient_id || '',
        };
        this.query = '';
        this.results = [];
        this.prefillFromProfile(item.id);
      },

      clearSelected() {
        this.selectedPatient = null;
        this.results = [];
        this.query = '';
      },

      prefillFromProfile(patientId) {
        const profileUrl = config.profileUrlTemplate.replace('/0/', `/${patientId}/`);
        fetch(profileUrl, {
          credentials: 'same-origin',
          headers: {
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then((r) => (r.ok ? r.json() : null))
          .then((profile) => {
            if (!profile) {
              return;
            }
            const mappings = config.fieldMappings || {};
            Object.entries(mappings).forEach(([fieldName, key]) => {
              const input = document.getElementById(`id_${fieldName}`);
              if (input && profile[key] !== undefined && profile[key] !== null) {
                input.value = profile[key];
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
              }
            });
          });
      },

      init() {
        if (this.selectedPatient?.id) {
          this.prefillFromProfile(this.selectedPatient.id);
        }
      },
    };
  }

  window.hfPatientPicker = hfPatientPickerFactory;

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('hfPatientPicker', hfPatientPickerFactory);
  });
})();
