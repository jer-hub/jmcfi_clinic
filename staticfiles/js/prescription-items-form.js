/**
 * Prescription medication row helpers — shared by create and edit flows.
 */
(function () {
  'use strict';

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text || ''));
    return div.innerHTML;
  }

  function getMedicationFormValues() {
    return {
      medication_name: (document.getElementById('new-medication-name') || {}).value || '',
      dosage: (document.getElementById('new-dosage') || {}).value || '',
      frequency: (document.getElementById('new-frequency') || {}).value || '',
      duration: (document.getElementById('new-duration') || {}).value || '',
      quantity: (document.getElementById('new-quantity') || {}).value || '',
      instructions: (document.getElementById('new-instructions') || {}).value || '',
    };
  }

  function clearMedicationForm() {
    ['new-medication-name', 'new-dosage', 'new-frequency', 'new-duration', 'new-quantity', 'new-instructions'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
  }

  function highlightMedicationNameError() {
    var nameEl = document.getElementById('new-medication-name');
    if (!nameEl) return;
    nameEl.focus();
    nameEl.classList.add('border-red-400', 'bg-red-50');
    setTimeout(function () {
      nameEl.classList.remove('border-red-400', 'bg-red-50');
    }, 2000);
  }

  function buildItemRowHtml(item) {
    var html = '<div id="item-' + item.id + '" class="prescription-item-row adding flex items-start gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">';
    html += '<div class="flex-1 min-w-0"><div class="flex items-center gap-2 flex-wrap">';
    html += '<span class="text-sm font-semibold text-gray-900">' + escapeHtml(item.medication_name) + '</span>';
    if (item.dosage) html += '<span class="text-xs bg-white px-2 py-0.5 rounded border border-gray-200 text-gray-600">' + escapeHtml(item.dosage) + '</span>';
    if (item.frequency) html += '<span class="text-xs text-gray-500">' + escapeHtml(item.frequency) + '</span>';
    if (item.duration) html += '<span class="text-xs text-gray-500">' + escapeHtml(item.duration) + '</span>';
    if (item.quantity) html += '<span class="text-xs bg-primary-50 px-2 py-0.5 rounded text-primary-700 font-medium">' + escapeHtml(item.quantity) + '</span>';
    html += '</div>';
    if (item.instructions) html += '<p class="text-xs text-gray-500 mt-1">' + escapeHtml(item.instructions) + '</p>';
    html += '</div>';
    html += '<button type="button" onclick="deletePrescriptionItem(' + item.id + ')" class="flex-shrink-0 p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" title="Remove">';
    html += '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
    html += '</button></div>';
    return html;
  }

  function appendItemRow(listEl, item) {
    if (!listEl || !item) return;
    var empty = listEl.querySelector('.text-center.py-6, .text-center.py-10');
    if (empty) empty.remove();
    if (!listEl.classList.contains('space-y-2')) {
      listEl.classList.add('space-y-2');
    }
    listEl.insertAdjacentHTML('beforeend', buildItemRowHtml(item));
  }

  function saveMedicationItem(addUrl, csrfToken) {
    var values = getMedicationFormValues();
    var name = values.medication_name.trim();
    if (!name) {
      return Promise.resolve({ success: false, error: 'Medication name is required.' });
    }

    var data = new URLSearchParams();
    Object.keys(values).forEach(function (key) {
      data.append(key, (values[key] || '').trim());
    });
    data.append('csrfmiddlewaretoken', csrfToken);

    return fetch(addUrl, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: data,
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return { ok: response.ok, data: payload };
        });
      })
      .then(function (result) {
        if (!result.ok || !result.data.success) {
          var errors = result.data.errors || {};
          var firstError = Object.keys(errors).length
            ? errors[Object.keys(errors)[0]][0]
            : (result.data.error || 'Could not save medication item.');
          return { success: false, error: firstError };
        }
        return { success: true, item: result.data.item };
      })
      .catch(function () {
        return { success: false, error: 'Network error while saving medication item.' };
      });
  }

  function showItemError(message) {
    var node = document.getElementById('prescription-item-form-error');
    if (node) {
      node.textContent = message;
      node.classList.remove('hidden');
      return;
    }
    window.alert(message);
  }

  function clearItemError() {
    var node = document.getElementById('prescription-item-form-error');
    if (!node) return;
    node.textContent = '';
    node.classList.add('hidden');
  }

  window.initPrescriptionEditItems = function initPrescriptionEditItems(config) {
    var addUrl = config.addUrl;
    var deleteUrlTemplate = config.deleteUrlTemplate;
    var listEl = document.getElementById(config.listId || 'prescription-items-list');
    var csrfToken = config.csrfToken;
    var form = document.querySelector(config.formSelector || 'form[data-section="details"]');

    window.addPrescriptionItem = function addPrescriptionItem() {
      clearItemError();
      saveMedicationItem(addUrl, csrfToken).then(function (result) {
        if (!result.success) {
          if (result.error && result.error.toLowerCase().indexOf('required') !== -1) {
            highlightMedicationNameError();
          }
          showItemError(result.error || 'Could not save medication item.');
          return;
        }
        appendItemRow(listEl, result.item);
        clearMedicationForm();
        var countLabel = document.getElementById('prescription-items-count');
        if (countLabel && listEl) {
          var count = listEl.querySelectorAll('.prescription-item-row').length;
          countLabel.textContent = '(' + count + ')';
        }
        var nameEl = document.getElementById('new-medication-name');
        if (nameEl) nameEl.focus();
      });
    };

    window.deletePrescriptionItem = function deletePrescriptionItem(itemId) {
      var row = document.getElementById('item-' + itemId);
      if (!row) return;
      row.classList.add('removing');
      setTimeout(function () {
        fetch(deleteUrlTemplate.replace('0', String(itemId)), {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (!data.success) return;
            row.remove();
            if (!listEl || listEl.querySelectorAll('.prescription-item-row').length > 0) return;
            listEl.innerHTML =
              '<div class="text-center py-6 text-sm text-gray-400 bg-gray-50 rounded-lg border border-dashed border-gray-300">' +
              '<svg class="w-8 h-8 mx-auto text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
              '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>' +
              'No prescription items yet. Add medications below.</div>';
            var countLabel = document.getElementById('prescription-items-count');
            if (countLabel) countLabel.textContent = '';
          });
      }, 200);
    };

    if (!form) return;

    form.addEventListener('submit', function (event) {
      if (form.dataset.rxItemFlush === '1') return;

      var nameEl = document.getElementById('new-medication-name');
      if (!nameEl || !nameEl.value.trim()) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      clearItemError();

      saveMedicationItem(addUrl, csrfToken).then(function (result) {
        if (!result.success) {
          showItemError(result.error || 'Could not save medication item.');
          return;
        }
        appendItemRow(listEl, result.item);
        clearMedicationForm();
        form.dataset.rxItemFlush = '1';
        form.requestSubmit();
        delete form.dataset.rxItemFlush;
      });
    }, true);
  };

  window.flushCreateMedicationRow = function flushCreateMedicationRow(addRowCallback) {
    var nameEl = document.getElementById('new-medication-name');
    if (!nameEl || !nameEl.value.trim() || typeof addRowCallback !== 'function') {
      return false;
    }
    addRowCallback();
    return true;
  };
})();
