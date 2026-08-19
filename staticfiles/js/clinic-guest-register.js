/**
 * Alpine panel: register a clinic guest patient via core API.
 */
(function () {
  function getCookie(name) {
    if (!document.cookie) {
      return null;
    }
    const parts = document.cookie.split(';');
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i].trim();
      if (part.indexOf(name + '=') === 0) {
        return decodeURIComponent(part.substring(name.length + 1));
      }
    }
    return null;
  }

  /** Normalize badge/local PH mobile display to E.164 (+639XXXXXXXXX) or ''. */
  function toE164Phone(raw) {
    const digits = String(raw || '').replace(/\D/g, '');
    if (!digits) return '';
    let mobile = '';
    if (digits.startsWith('63') && digits.length >= 12) mobile = digits.slice(2, 12);
    else if (digits.startsWith('0') && digits.length >= 11) mobile = digits.slice(1, 11);
    else if (digits.startsWith('9')) mobile = digits.slice(0, 10);
    else mobile = digits.slice(0, 10);
    return mobile.length === 10 ? '+63' + mobile : '';
  }

  function clinicGuestPanelFactory(config) {
    config = config || {};
    const mode = (config.mode === 'defer' || config.mode === 'collect') ? config.mode : 'instant';

    return {
      mode,
      guestOpen: Boolean(config.initialOpen),
      guestFirstName: config.initialFirstName || '',
      guestLastName: config.initialLastName || '',
      guestEmail: config.initialEmail || '',
      guestPhone: config.initialPhone || '',
      guestSubmitting: false,
      guestError: '',

      init() {
        if (this.guestOpen) {
          this.$dispatch('clinic-guest-toggled', { open: true });
        }
      },

      toggleGuestPanel() {
        this.setGuestOpen(!this.guestOpen);
      },

      setGuestOpen(open) {
        const next = !!open;
        this.guestError = '';
        if (!next) {
          this.guestOpen = false;
          this.guestFirstName = '';
          this.guestLastName = '';
          this.guestEmail = '';
          this.guestPhone = '';
          this.$dispatch('clinic-guest-toggled', { open: false });
          return;
        }
        this.guestOpen = true;
        this.$dispatch('clinic-guest-toggled', { open: true });
      },

      async submitGuest(options) {
        options = options || {};
        if (this.mode !== 'instant') {
          return;
        }
        const first = (options.firstName || this.guestFirstName || '').trim();
        const last = (options.lastName || this.guestLastName || '').trim();
        const email = (options.email || this.guestEmail || '').trim();
        if (!first || !last) {
          this.guestError = 'First and last name are required.';
          return;
        }
        if (this.mode === 'instant' && !email) {
          this.guestError = 'Contact email is required for guest notifications.';
          return;
        }
        this.guestSubmitting = true;
        this.guestError = '';
        const body = {
          clinical_module: config.clinicalModule,
          first_name: first,
          last_name: last,
        };
        if (email) {
          body.email = email;
        }
        const phoneRaw =
          options.phone ||
          (this.$refs && this.$refs.guestPhoneInput
            ? this.$refs.guestPhoneInput.value
            : this.guestPhone) ||
          '';
        const phone = toE164Phone(phoneRaw);
        if (String(phoneRaw || '').replace(/\D/g, '').length > 0 && !phone) {
          this.guestError =
            'Enter a valid 10-digit mobile number (e.g. 917 123 4567), or leave it blank.';
          this.guestSubmitting = false;
          return;
        }
        if (phone) {
          body.phone = phone;
        }
        try {
          const res = await fetch(config.registerUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              'Content-Type': 'application/json',
              Accept: 'application/json',
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': getCookie('csrftoken') || '',
            },
            body: JSON.stringify(body),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            this.guestError = data.error || 'Could not register guest patient.';
            return;
          }
          this.guestOpen = false;
          this.guestFirstName = '';
          this.guestLastName = '';
          this.guestEmail = '';
          this.guestPhone = '';
          this.$dispatch('clinic-guest-toggled', { open: false });
          this.$dispatch('clinic-guest-created', data);
        } catch {
          this.guestError = 'Network error. Please try again.';
        } finally {
          this.guestSubmitting = false;
        }
      },
    };
  }

  window.clinicGuestPanel = clinicGuestPanelFactory;

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('clinicGuestPanel', clinicGuestPanelFactory);
  });
})();
