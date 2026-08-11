/**
 * Sync consent checkboxes with paired date inputs (local today).
 * Prefer [data-consent-date-for="dateInputId"] on the checkbox; falls back to default ids.
 */
(function () {
  function todayLocalISO() {
    var d = new Date();
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function wireConsent(cb, dt) {
    if (!cb || !dt) return;

    function syncFromCheckbox() {
      if (cb.checked) {
        dt.value = todayLocalISO();
      } else {
        dt.value = '';
      }
    }

    if (cb.checked && !dt.value) {
      dt.value = todayLocalISO();
    }
    cb.addEventListener('change', syncFromCheckbox);
  }

  function wireByIds(checkboxId, dateId) {
    wireConsent(document.getElementById(checkboxId), document.getElementById(dateId));
  }

  window.jmcfiWireConsentDates = function (pairs) {
    (pairs || []).forEach(function (pair) {
      if (!pair || pair.length < 2) return;
      wireByIds(pair[0], pair[1]);
    });
  };

  document.addEventListener('DOMContentLoaded', function () {
    var wired = false;
    document.querySelectorAll('[data-consent-date-for]').forEach(function (cb) {
      var dateId = cb.getAttribute('data-consent-date-for');
      if (!dateId) return;
      wireConsent(cb, document.getElementById(dateId));
      wired = true;
    });
    if (!wired) {
      window.jmcfiWireConsentDates([
        ['id_consent_signed', 'id_consent_date'],
        ['id_informed_consent_signed', 'id_informed_consent_date'],
      ]);
    }
  });
})();
