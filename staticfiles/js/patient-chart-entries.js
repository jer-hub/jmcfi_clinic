/**
 * Patient Chart consultation log — add, edit, and delete entries via JSON API.
 */
(function () {
  'use strict';

  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function pad2(n) {
    return String(n).padStart(2, '0');
  }

  function nowLocalDateTime() {
    var d = new Date();
    d.setSeconds(0, 0);
    return (
      d.getFullYear() +
      '-' +
      pad2(d.getMonth() + 1) +
      '-' +
      pad2(d.getDate()) +
      'T' +
      pad2(d.getHours()) +
      ':' +
      pad2(d.getMinutes())
    );
  }

  function clearEntryErrors(form) {
    form.querySelectorAll('[data-entry-error]').forEach(function (el) {
      el.textContent = '';
      el.classList.add('hidden');
    });
  }

  function showEntryErrors(form, errors) {
    Object.keys(errors || {}).forEach(function (field) {
      var node = form.querySelector('[data-entry-error="' + field + '"]');
      if (!node) return;
      var messages = errors[field];
      node.textContent = Array.isArray(messages) ? messages.join(' ') : messages;
      node.classList.remove('hidden');
      if (field === '__all__') {
        node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }

  function parseJsonResponse(response) {
    return response.text().then(function (text) {
      if (!text) {
        return { ok: response.ok, data: { success: false, error: 'Empty server response.' } };
      }
      try {
        return { ok: response.ok, data: JSON.parse(text) };
      } catch (err) {
        return { ok: false, data: { success: false, error: 'Unexpected server response.' } };
      }
    });
  }

  function updateCountLabel(labelEl, count) {
    if (!labelEl) return;
    labelEl.textContent = count + ' entr' + (count === 1 ? 'y' : 'ies');
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  function displayCellText(value) {
    var text = (value || '').trim();
    return text || '—';
  }

  function toggleEmptyState(emptyEl, tableWrap, hasRows) {
    if (emptyEl) emptyEl.classList.toggle('hidden', hasRows);
    if (tableWrap) tableWrap.classList.toggle('hidden', !hasRows);
  }

  function buildRowHtml(entry, canManage) {
    var actions = '';
    if (canManage) {
      actions =
        '<td class="px-4 py-3 text-right whitespace-nowrap align-top">' +
          '<button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 hover:bg-indigo-50 hover:text-indigo-700 transition-colors entry-edit-btn" title="Edit entry" aria-label="Edit entry">' +
            '<i class="fas fa-pen text-xs" aria-hidden="true"></i></button>' +
          '<button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 hover:bg-red-50 hover:text-red-700 transition-colors entry-delete-btn" title="Delete entry" aria-label="Delete entry">' +
            '<i class="fas fa-trash text-xs" aria-hidden="true"></i></button>' +
        '</td>';
    }
    return (
      '<td class="px-4 py-3 whitespace-nowrap text-gray-900 tabular-nums align-top">' + escapeHtml(entry.date_and_time) + '</td>' +
      '<td class="px-4 py-3 text-gray-700 whitespace-pre-wrap align-top entry-findings-cell">' + escapeHtml(displayCellText(entry.findings)) + '</td>' +
      '<td class="px-4 py-3 text-gray-700 whitespace-pre-wrap align-top entry-orders-cell">' + escapeHtml(displayCellText(entry.doctors_orders)) + '</td>' +
      '<td class="px-4 py-3 text-gray-600 align-top entry-recorded-by-cell">' + escapeHtml(entry.recorded_by || '—') + '</td>' +
      actions
    );
  }

  function applyRowData(row, entry) {
    row.dataset.entryId = entry.id;
    row.dataset.updateUrl = entry.update_url || row.dataset.updateUrl || '';
    row.dataset.deleteUrl = entry.delete_url || row.dataset.deleteUrl || '';
    row.dataset.dateInput = entry.date_and_time_input || row.dataset.dateInput || '';
    row.cells[0].textContent = entry.date_and_time;
    row.querySelector('.entry-findings-cell').textContent = displayCellText(entry.findings);
    row.querySelector('.entry-orders-cell').textContent = displayCellText(entry.doctors_orders);
    var recordedByCell = row.querySelector('.entry-recorded-by-cell');
    if (recordedByCell && entry.recorded_by) {
      recordedByCell.textContent = entry.recorded_by;
    }
  }

  window.initPatientChartEntries = function initPatientChartEntries(config) {
    var form = document.getElementById(config.formId);
    var tbody = document.getElementById(config.tableBodyId);
    if (!form || !tbody) return;
    if (form.dataset.chartEntriesBound === '1') return;
    form.dataset.chartEntriesBound = '1';

    var emptyEl = document.getElementById(config.emptyStateId);
    var tableWrap = document.getElementById(config.tableWrapId);
    var countLabel = document.getElementById(config.countLabelId);
    var csrfToken = getCookie('csrftoken');
    var entryIdInput = document.getElementById(config.entryIdInputId);
    var submitButton = document.getElementById(config.submitButtonId);
    var submitLabel = submitButton ? submitButton.querySelector('span') : null;
    var editBanner = document.getElementById(config.editModeBannerId);
    var cancelEditButton = document.getElementById(config.cancelEditButtonId);
    var dateInput = document.getElementById(config.dateInputId);
    var findingsInput = document.getElementById(config.findingsInputId);
    var ordersInput = document.getElementById(config.ordersInputId);
    var dateInitialInput = form.querySelector('input[name="initial-date_and_time"]');
    var defaultDateTime = config.defaultDateTime || '';
    var canManage = Boolean(submitButton);
    var submitting = false;

    function syncDateTimeInitial(value) {
      if (dateInitialInput) {
        dateInitialInput.value = value;
      }
    }

    function setDefaultDateTime() {
      var value = defaultDateTime || nowLocalDateTime();
      if (dateInput) {
        dateInput.value = value;
      }
      syncDateTimeInitial(value);
      return value;
    }

    function ensureDateTimeForSubmit() {
      if (!dateInput) return;
      if (!dateInput.value.trim()) {
        setDefaultDateTime();
        return;
      }
      syncDateTimeInitial(dateInput.value);
    }

    function resetFormMode() {
      if (entryIdInput) entryIdInput.value = '';
      if (editBanner) editBanner.classList.add('hidden');
      if (submitLabel) submitLabel.textContent = 'Add entry';
      if (submitButton) {
        submitButton.querySelector('i').className = 'fas fa-plus';
      }
      if (findingsInput) findingsInput.value = '';
      if (ordersInput) ordersInput.value = '';
      setDefaultDateTime();
      tbody.querySelectorAll('tr').forEach(function (row) {
        row.classList.remove('ring-2', 'ring-indigo-200', 'bg-indigo-50/40');
      });
    }

    function setEditMode(row) {
      if (!entryIdInput || !dateInput || !findingsInput || !ordersInput) return;
      entryIdInput.value = row.dataset.entryId || '';
      var dateValue = row.dataset.dateInput || '';
      dateInput.value = dateValue;
      syncDateTimeInitial(dateValue);
      var findingsCell = row.querySelector('.entry-findings-cell');
      var ordersCell = row.querySelector('.entry-orders-cell');
      findingsInput.value = findingsCell && findingsCell.textContent.trim() !== '—' ? findingsCell.textContent.trim() : '';
      ordersInput.value = ordersCell && ordersCell.textContent.trim() !== '—' ? ordersCell.textContent.trim() : '';
      if (editBanner) editBanner.classList.remove('hidden');
      if (submitLabel) submitLabel.textContent = 'Save changes';
      if (submitButton) {
        submitButton.querySelector('i').className = 'fas fa-floppy-disk';
      }
      tbody.querySelectorAll('tr').forEach(function (tr) {
        tr.classList.toggle('ring-2', tr === row);
        tr.classList.toggle('ring-indigo-200', tr === row);
        tr.classList.toggle('bg-indigo-50/40', tr === row);
      });
      form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      findingsInput.focus();
    }

    setDefaultDateTime();

    if (cancelEditButton) {
      cancelEditButton.addEventListener('click', function () {
        clearEntryErrors(form);
        resetFormMode();
      });
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (submitting) return;

      clearEntryErrors(form);
      ensureDateTimeForSubmit();

      var findings = findingsInput ? findingsInput.value.trim() : '';
      var orders = ordersInput ? ordersInput.value.trim() : '';
      if (!findings && !orders) {
        showEntryErrors(form, {
          __all__: ["Enter findings, doctor's orders, or both before saving this entry."],
        });
        if (findingsInput) findingsInput.focus();
        return;
      }

      var entryId = entryIdInput ? entryIdInput.value : '';
      var targetUrl = config.addUrl;
      var editingRow = entryId ? tbody.querySelector('[data-entry-id="' + entryId + '"]') : null;
      if (entryId && editingRow && editingRow.dataset.updateUrl) {
        targetUrl = editingRow.dataset.updateUrl;
      }

      submitting = true;
      if (submitButton) submitButton.disabled = true;

      fetch(targetUrl, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken,
        },
        body: new FormData(form),
      })
        .then(parseJsonResponse)
        .then(function (result) {
          if (!result.ok || !result.data.success) {
            showEntryErrors(form, result.data.errors || { __all__: [result.data.error || 'Could not save entry.'] });
            return;
          }

          var entry = result.data.entry;
          if (entryId && editingRow) {
            applyRowData(editingRow, entry);
            resetFormMode();
            return;
          }

          var row = document.createElement('tr');
          row.className = 'hover:bg-gray-50/80 transition-colors';
          row.dataset.entryId = entry.id;
          row.dataset.updateUrl = entry.update_url || '';
          row.dataset.deleteUrl = entry.delete_url || '';
          row.dataset.dateInput = entry.date_and_time_input || '';
          row.innerHTML = buildRowHtml(entry, canManage);
          tbody.prepend(row);
          resetFormMode();
          var count = tbody.querySelectorAll('tr').length;
          updateCountLabel(countLabel, count);
          toggleEmptyState(emptyEl, tableWrap, count > 0);
        })
        .catch(function () {
          showEntryErrors(form, { __all__: ['Network error. Please try again.'] });
        })
        .finally(function () {
          submitting = false;
          if (submitButton) submitButton.disabled = false;
        });
    });

    tbody.addEventListener('click', function (event) {
      var editBtn = event.target.closest('.entry-edit-btn');
      if (editBtn) {
        var editRow = editBtn.closest('tr');
        if (editRow) setEditMode(editRow);
        return;
      }

      var btn = event.target.closest('.entry-delete-btn');
      if (!btn) return;
      if (!window.confirm('Delete this consultation entry?')) return;

      var row = btn.closest('tr');
      var deleteUrl = row ? row.dataset.deleteUrl : '';
      if (!deleteUrl) return;

      if (entryIdInput && entryIdInput.value && row && row.dataset.entryId === entryIdInput.value) {
        resetFormMode();
      }

      fetch(deleteUrl, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken,
        },
      })
        .then(parseJsonResponse)
        .then(function (result) {
          if (!result.ok || !result.data.success) return;
          if (row) row.remove();
          var count = tbody.querySelectorAll('tr').length;
          updateCountLabel(countLabel, count);
          toggleEmptyState(emptyEl, tableWrap, count > 0);
        });
    });
  };
})();
