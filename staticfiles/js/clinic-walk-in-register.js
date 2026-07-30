/**
 * Alpine panel: register a clinic walk-in guest via core API.
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

  function clinicWalkInGuestPanelFactory(config) {
    config = config || {};
    return {
      walkInOpen: false,
      walkInFirstName: '',
      walkInLastName: '',
      walkInPhone: '',
      walkInSubmitting: false,
      walkInError: '',

      toggleWalkInPanel() {
        this.walkInOpen = !this.walkInOpen;
        this.walkInError = '';
      },

      async submitWalkInGuest() {
        const first = (this.walkInFirstName || '').trim();
        const last = (this.walkInLastName || '').trim();
        if (!first || !last) {
          this.walkInError = 'First and last name are required.';
          return;
        }
        this.walkInSubmitting = true;
        this.walkInError = '';
        const body = {
          clinical_module: config.clinicalModule,
          first_name: first,
          last_name: last,
        };
        const phone = (this.walkInPhone || '').trim();
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
            this.walkInError = data.error || 'Could not register walk-in guest.';
            return;
          }
          this.walkInOpen = false;
          this.walkInFirstName = '';
          this.walkInLastName = '';
          this.walkInPhone = '';
          this.$dispatch('clinic-walk-in-created', data);
        } catch {
          this.walkInError = 'Network error. Please try again.';
        } finally {
          this.walkInSubmitting = false;
        }
      },
    };
  }

  window.clinicWalkInGuestPanel = clinicWalkInGuestPanelFactory;

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('clinicWalkInGuestPanel', clinicWalkInGuestPanelFactory);
  });
})();
