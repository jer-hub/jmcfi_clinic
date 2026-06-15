/**
 * Global HTMX handler for 401/403 access denials.
 * Ensures HX-Redirect triggers a full-page navigation (not a fragment swap).
 */
(function () {
  const RESTRICTED_FALLBACK = '/access/restricted/';

  function redirectFromXhr(xhr) {
    if (!xhr) {
      return false;
    }
    const headerUrl = xhr.getResponseHeader('HX-Redirect');
    if (headerUrl) {
      window.location.assign(headerUrl);
      return true;
    }
    const status = xhr.status;
    if (status === 401) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.assign('/accounts/login/?next=' + next);
      return true;
    }
    if (status === 403) {
      const reason = xhr.getResponseHeader('X-Access-Denied-Reason') || 'forbidden';
      window.location.assign(
        RESTRICTED_FALLBACK + '?reason=' + encodeURIComponent(reason),
      );
      return true;
    }
    return false;
  }

  function attachListeners() {
    document.addEventListener('htmx:responseError', function (event) {
      const xhr = event.detail && event.detail.xhr;
      if (!xhr || (xhr.status !== 401 && xhr.status !== 403)) {
        return;
      }
      if (redirectFromXhr(xhr)) {
        event.preventDefault();
      }
    });

    document.addEventListener('access-denied', function (event) {
      const detail = (event.detail && event.detail.value) || event.detail || {};
      if (detail.redirect) {
        window.location.assign(detail.redirect);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachListeners);
  } else {
    attachListeners();
  }
})();
