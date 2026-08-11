/**
 * Alpine.js data factory for health-forms patient search + profile prefill.
 */
(function () {
  function isListField(fieldName) {
    return Boolean(
      window.__hfListFields?.[fieldName] ||
      document.querySelector(`[data-list-field="${fieldName}"]`),
    );
  }

  function applyPrefillValue(fieldName, value) {
    if (value === undefined || value === null) {
      return;
    }
    const stringValue = String(value);

    if (
      isListField(fieldName) &&
      typeof window.hfReloadListField === 'function' &&
      window.hfReloadListField(fieldName, stringValue)
    ) {
      return;
    }

    const input = document.getElementById(`id_${fieldName}`);
    if (!input) {
      return;
    }

    if (
      input.tagName === 'SELECT' &&
      stringValue &&
      !Array.from(input.options || []).some((opt) => String(opt.value) === stringValue)
    ) {
      input.dataset.prefillValue = stringValue;
    }

    input.value = stringValue;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function syncAcademicInstitutionalFromDom() {
    const roots = document.querySelectorAll('[data-academic-fieldset]');
    roots.forEach((root) => {
      if (!window.Alpine || typeof window.Alpine.$data !== 'function') {
        return;
      }
      let data;
      try {
        data = window.Alpine.$data(root);
      } catch (_) {
        return;
      }
      if (data && typeof data.syncFromExternalPrefill === 'function') {
        data.syncFromExternalPrefill();
      }
    });
  }

  function hfPatientPickerFactory(config) {
    config = config || {};
    return {
      query: '',
      loading: false,
      results: [],
      searchSeq: 0,
      activeSearch: 0,
      selectedPatient: config.initialSelected || null,
      guestRegisterOpen: false,

      onGuestToggled(detail) {
        this.guestRegisterOpen = !!(detail && detail.open);
        if (this.guestRegisterOpen) {
          this.clearSelected();
        }
      },

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
            const applyAll = () => {
              Object.entries(mappings).forEach(([fieldName, key]) => {
                applyPrefillValue(fieldName, profile[key]);
              });
              syncAcademicInstitutionalFromDom();
            };
            applyAll();
            if (window.Alpine && typeof window.Alpine.nextTick === 'function') {
              window.Alpine.nextTick(applyAll);
            }
            window.setTimeout(applyAll, 50);
          });
      },

      init() {
        if (this.selectedPatient?.id) {
          this.prefillFromProfile(this.selectedPatient.id);
        }
      },

      onGuestCreated(patient) {
        if (!patient || !patient.id) {
          return;
        }
        this.selectPatient({
          id: patient.id,
          name: patient.name,
          email: patient.email,
          patient_id: patient.patient_id,
        });
      },
    };
  }

  window.hfPatientPicker = hfPatientPickerFactory;
  window.hfApplyPrefillValue = applyPrefillValue;
  window.hfSyncAcademicInstitutionalFromDom = syncAcademicInstitutionalFromDom;

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('hfPatientPicker', hfPatientPickerFactory);
  });
})();
