/**
 * Health form tabbed edit: AJAX section save, dirty tracking, tab switch guard.
 */
(function () {
  'use strict';

  var dirty = {};
  var pendingLeaveAction = null;
  var sectionSnapshots = {};
  var suppressDirty = false;
  var allowUnload = false;

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

  function getActiveSection() {
    var fromUrl = new URL(window.location.href).searchParams.get('section');
    if (fromUrl) return fromUrl;
    var visiblePanel = document.querySelector('[data-tab-panel]:not(.hidden)');
    if (visiblePanel) return visiblePanel.getAttribute('data-tab-panel');
    var firstForm = document.querySelector('form[data-section]');
    return firstForm ? firstForm.getAttribute('data-section') : null;
  }

  function getFormForSection(section) {
    return document.querySelector('form[data-section="' + section + '"]');
  }

  function hasUnsavedChanges() {
    return Object.keys(dirty).some(function (key) {
      return dirty[key];
    });
  }

  function setTabStatus(section, status) {
    var badge = document.querySelector('[data-tab-badge="' + section + '"]');
    if (!badge) return;
    badge.classList.remove('hidden', 'text-amber-500', 'text-success-600', 'text-red-500');
    badge.innerHTML = '';
    if (status === 'unsaved') {
      badge.classList.remove('hidden');
      badge.classList.add('text-amber-500');
      badge.innerHTML = '<i class="fas fa-circle text-[6px] align-middle" aria-hidden="true"></i>';
      badge.setAttribute('title', 'Unsaved changes');
    } else if (status === 'saved') {
      badge.classList.remove('hidden');
      badge.classList.add('text-success-600');
      badge.innerHTML = '<i class="fas fa-check text-xs" aria-hidden="true"></i>';
      badge.setAttribute('title', 'Saved');
    } else if (status === 'error') {
      badge.classList.remove('hidden');
      badge.classList.add('text-red-500');
      badge.innerHTML = '<i class="fas fa-circle-exclamation text-xs" aria-hidden="true"></i>';
      badge.setAttribute('title', 'Has errors');
    } else if (status === 'none' || !status) {
      badge.classList.add('hidden');
      badge.removeAttribute('title');
    } else {
      badge.classList.add('hidden');
      badge.removeAttribute('title');
    }
  }

  function markDirty(section) {
    if (suppressDirty || !section) return;
    dirty[section] = true;
    setTabStatus(section, 'unsaved');
  }

  function markClean(section) {
    if (!section) return;
    dirty[section] = false;
    setTabStatus(section, 'saved');
  }

  function switchToSection(targetKey, skipDirtyCheck) {
    if (!targetKey) return;
    var active = getActiveSection();
    if (!skipDirtyCheck && active && dirty[active] && targetKey !== active) {
      promptLeave({ type: 'tab', target: targetKey });
      return false;
    }
    var tabs = document.querySelectorAll('[data-tab]');
    var panels = document.querySelectorAll('[data-tab-panel]');
    tabs.forEach(function (t) {
      var isActive = t.getAttribute('data-tab') === targetKey;
      t.setAttribute('aria-selected', isActive ? 'true' : 'false');
      t.classList.toggle('text-primary-600', isActive);
      t.classList.toggle('border-b-2', isActive);
      t.classList.toggle('border-primary-600', isActive);
      t.classList.toggle('bg-primary-50/50', isActive);
      t.classList.toggle('text-gray-500', !isActive);
    });
    panels.forEach(function (p) {
      p.classList.toggle('hidden', p.getAttribute('data-tab-panel') !== targetKey);
    });
    var url = new URL(window.location.href);
    url.searchParams.set('section', targetKey);
    window.history.replaceState({}, '', url);
    return true;
  }

  function getUnsavedModal() {
    return document.getElementById('unsaved-changes-modal');
  }

  function configureUnsavedModal(action) {
    var modal = getUnsavedModal();
    if (!modal) return;
    var prompt = modal.querySelector('[data-unsaved-modal-prompt]');
    var saveBtn = document.getElementById('unsaved-save-switch');
    var discardBtn = document.getElementById('unsaved-discard-switch');
    var stayBtn = document.getElementById('unsaved-stay');

    if (action && action.type === 'reload') {
      if (prompt) {
        prompt.textContent = 'You have unsaved changes. Reloading will discard them unless you save first.';
      }
      if (saveBtn) saveBtn.innerHTML = '<i class="fas fa-floppy-disk mr-1.5"></i>Save &amp; reload';
      if (discardBtn) discardBtn.innerHTML = '<i class="fas fa-rotate-right mr-1.5"></i>Discard &amp; reload';
      if (stayBtn) stayBtn.textContent = 'Stay on this page';
      return;
    }

    if (action && action.type === 'navigate') {
      if (prompt) {
        prompt.textContent = 'You have unsaved changes. Leaving will discard them unless you save first.';
      }
      if (saveBtn) saveBtn.innerHTML = '<i class="fas fa-floppy-disk mr-1.5"></i>Save &amp; leave';
      if (discardBtn) discardBtn.innerHTML = '<i class="fas fa-arrow-right mr-1.5"></i>Discard &amp; leave';
      if (stayBtn) stayBtn.textContent = 'Stay on this page';
      return;
    }

    if (prompt) {
      prompt.textContent = prompt.getAttribute('data-default-prompt') || prompt.textContent;
    }
    if (saveBtn && saveBtn.getAttribute('data-default-html')) {
      saveBtn.innerHTML = saveBtn.getAttribute('data-default-html');
    }
    if (discardBtn && discardBtn.getAttribute('data-default-html')) {
      discardBtn.innerHTML = discardBtn.getAttribute('data-default-html');
    }
    if (stayBtn && stayBtn.getAttribute('data-default-html')) {
      stayBtn.innerHTML = stayBtn.getAttribute('data-default-html');
    }
  }

  function resetUnsavedModal() {
    var modal = getUnsavedModal();
    if (!modal) return;
    var status = modal.querySelector('[data-unsaved-modal-status]');
    var prompt = modal.querySelector('[data-unsaved-modal-prompt]');
    var actions = modal.querySelector('[data-unsaved-modal-actions]');
    if (status) {
      status.className = 'hidden mt-3 rounded-lg px-3 py-2 text-sm font-medium';
      status.textContent = '';
    }
    if (prompt) prompt.classList.remove('hidden');
    if (actions) actions.classList.remove('hidden');
    ['unsaved-save-switch', 'unsaved-discard-switch', 'unsaved-stay'].forEach(function (id) {
      var btn = document.getElementById(id);
      if (!btn) return;
      btn.disabled = false;
      if (btn.getAttribute('data-default-html')) {
        btn.innerHTML = btn.getAttribute('data-default-html');
      }
    });
    configureUnsavedModal({ type: 'tab' });
  }

  function setUnsavedModalButtonsDisabled(disabled) {
    ['unsaved-save-switch', 'unsaved-discard-switch', 'unsaved-stay'].forEach(function (id) {
      var btn = document.getElementById(id);
      if (btn) btn.disabled = disabled;
    });
  }

  function setUnsavedModalStatus(message, type) {
    var modal = getUnsavedModal();
    if (!modal) return;
    var status = modal.querySelector('[data-unsaved-modal-status]');
    if (!status) return;
    status.classList.remove('hidden', 'bg-red-50', 'text-red-800', 'bg-green-50', 'text-green-800', 'bg-primary-50', 'text-primary-800');
    if (type === 'success') {
      status.classList.add('bg-green-50', 'text-green-800');
    } else if (type === 'error') {
      status.classList.add('bg-red-50', 'text-red-800');
    } else {
      status.classList.add('bg-primary-50', 'text-primary-800');
    }
    status.textContent = message;
  }

  function showUnsavedModal() {
    var modal = getUnsavedModal();
    if (!modal) return;
    resetUnsavedModal();
    configureUnsavedModal(pendingLeaveAction);
    modal.style.display = 'block';
    modal.setAttribute('aria-hidden', 'false');
  }

  function hideUnsavedModal() {
    var modal = getUnsavedModal();
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    resetUnsavedModal();
  }

  function clearPendingLeaveAction() {
    pendingLeaveAction = null;
  }

  function promptLeave(action) {
    pendingLeaveAction = action;
    showUnsavedModal();
  }

  function completeLeaveAfterDiscard() {
    var action = pendingLeaveAction;
    var active = getActiveSection();
    if (active) discardSectionChanges(active);
    hideUnsavedModal();
    allowUnload = true;
    clearPendingLeaveAction();

    if (action && action.type === 'tab' && action.target) {
      switchToSection(action.target, true);
    } else if (action && action.type === 'reload') {
      window.location.reload();
    } else if (action && action.type === 'navigate' && action.href) {
      window.location.assign(action.href);
    }
  }

  function completeLeaveAfterSave() {
    var action = pendingLeaveAction;
    hideUnsavedModal();
    clearPendingLeaveAction();
    allowUnload = true;

    if (action && action.type === 'reload') {
      window.location.reload();
    } else if (action && action.type === 'navigate' && action.href) {
      window.location.assign(action.href);
    } else if (action && action.type === 'tab' && action.target) {
      switchToSection(action.target, true);
    }
  }

  function escapeFieldName(name) {
    if (window.CSS && CSS.escape) return CSS.escape(name);
    return name.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function getFormFieldNames(form) {
    var names = [];
    var seen = {};
    form.querySelectorAll('[name]').forEach(function (el) {
      if (!el.name || el.name === 'csrfmiddlewaretoken' || seen[el.name]) return;
      seen[el.name] = true;
      names.push(el.name);
    });
    return names;
  }

  function getAlpineComponentData(form) {
    if (typeof Alpine !== 'undefined' && typeof Alpine.$data === 'function') {
      try {
        return Alpine.$data(form);
      } catch (e) {
        /* Alpine not bound yet */
      }
    }
    if (form._x_dataStack && form._x_dataStack.length) {
      return form._x_dataStack[0];
    }
    return null;
  }

  function captureAlpineSnapshot(form) {
    var data = getAlpineComponentData(form);
    if (!data) return null;
    if (data.immunizationFlags) {
      return { type: 'immunization', flags: JSON.parse(JSON.stringify(data.immunizationFlags)) };
    }
    if (data.diagnosticFlags) {
      return { type: 'diagnostic', flags: JSON.parse(JSON.stringify(data.diagnosticFlags)) };
    }
    return null;
  }

  function restoreAlpineSnapshot(form, alpineSnap) {
    if (!alpineSnap) return;
    var data = getAlpineComponentData(form);
    if (!data) return;
    var target = alpineSnap.type === 'immunization' ? data.immunizationFlags : data.diagnosticFlags;
    if (!target) return;
    Object.keys(target).forEach(function (key) {
      delete target[key];
    });
    Object.assign(target, alpineSnap.flags);
  }

  function captureFieldState(form, name) {
    var nodes = form.querySelectorAll('[name="' + escapeFieldName(name) + '"]');
    if (!nodes.length) return null;
    var first = nodes[0];
    if (first.type === 'checkbox') {
      if (nodes.length === 1) {
        return { type: 'checkbox', checked: first.checked };
      }
      var values = [];
      nodes.forEach(function (node) {
        if (node.checked) values.push(node.value);
      });
      return { type: 'checkbox-group', values: values };
    }
    if (first.type === 'radio') {
      var selected = '';
      nodes.forEach(function (node) {
        if (node.checked) selected = node.value;
      });
      return { type: 'radio', value: selected };
    }
    if (first.tagName === 'SELECT' && first.multiple) {
      return {
        type: 'multi',
        values: Array.from(first.selectedOptions).map(function (option) {
          return option.value;
        }),
      };
    }
    return { type: 'value', value: first.value };
  }

  function applyFieldState(form, name, state) {
    if (!state) return;
    var nodes = form.querySelectorAll('[name="' + escapeFieldName(name) + '"]');
    if (!nodes.length) return;

    if (state.type === 'checkbox') {
      nodes[0].checked = !!state.checked;
      return;
    }
    if (state.type === 'checkbox-group') {
      nodes.forEach(function (node) {
        node.checked = state.values.indexOf(node.value) !== -1;
      });
      return;
    }
    if (state.type === 'radio') {
      nodes.forEach(function (node) {
        node.checked = node.value === state.value;
      });
      return;
    }
    if (state.type === 'multi') {
      Array.from(nodes[0].options).forEach(function (option) {
        option.selected = state.values.indexOf(option.value) !== -1;
      });
      return;
    }
    nodes[0].value = state.value != null ? state.value : '';
  }

  function saveSectionSnapshot(section) {
    var form = getFormForSection(section);
    if (!form) return;
    enableDisabledFields(form);
    var fields = {};
    getFormFieldNames(form).forEach(function (name) {
      fields[name] = captureFieldState(form, name);
    });
    sectionSnapshots[section] = {
      fields: fields,
      alpine: captureAlpineSnapshot(form),
    };
  }

  function discardSectionChanges(section) {
    var form = getFormForSection(section);
    var snapshot = sectionSnapshots[section];
    if (!form || !snapshot) return false;

    suppressDirty = true;
    if (snapshot.alpine) restoreAlpineSnapshot(form, snapshot.alpine);
    Object.keys(snapshot.fields).forEach(function (name) {
      applyFieldState(form, name, snapshot.fields[name]);
    });
    clearFieldErrors(form);
    form.querySelectorAll('input, select, textarea').forEach(function (el) {
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    });
    suppressDirty = false;
    dirty[section] = false;
    setTabStatus(section, 'none');
    return true;
  }

  function enableDisabledFields(form) {
    form.querySelectorAll(':disabled').forEach(function (el) {
      el.disabled = false;
    });
  }

  function findFieldWrapper(input) {
    if (!input) return null;
    return input.closest('[data-field-wrapper]') || input.closest('.has-error') || input.parentElement;
  }

  function clearFieldErrors(form) {
    form.querySelectorAll('.has-error').forEach(function (el) {
      el.classList.remove('has-error');
    });
    form.querySelectorAll('[data-field-error]').forEach(function (el) {
      el.remove();
    });
    var banner = form.querySelector('[data-section-error-banner]');
    if (banner) {
      banner.classList.add('hidden');
      banner.classList.remove('flex');
      banner.innerHTML = '';
    }
  }

  function applyFieldErrors(form, errors) {
    var count = 0;
    var firstInput = null;
    Object.keys(errors || {}).forEach(function (fieldName) {
      var messages = errors[fieldName];
      if (!messages || !messages.length) return;
      var input = form.querySelector('[name="' + escapeFieldName(fieldName) + '"]');
      if (!input) return;
      if (!firstInput) firstInput = input;
      count += 1;
      var wrapper = findFieldWrapper(input);
      if (wrapper) {
        wrapper.classList.add('has-error');
        var errEl = document.createElement('p');
        errEl.className = 'mt-1 text-xs text-red-600 font-medium';
        errEl.setAttribute('data-field-error', 'true');
        errEl.textContent = messages[0];
        wrapper.appendChild(errEl);
      }
    });
    var banner = form.querySelector('[data-section-error-banner]');
    if (banner && count > 0) {
      banner.classList.remove('hidden');
      banner.classList.add('flex');
      banner.setAttribute('role', 'alert');
      banner.innerHTML =
        '<svg class="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">' +
        '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>' +
        '<p class="text-sm font-medium text-red-800">Please fix <strong>' + count + '</strong> field error' + (count === 1 ? '' : 's') + ' below.</p>';
    }
    return { count: count, firstInput: firstInput };
  }

  function focusFirstFieldError(form) {
    var target =
      form.querySelector('.has-error input:not([type="hidden"]), .has-error select, .has-error textarea') ||
      form.querySelector('input.has-error, select.has-error, textarea.has-error');
    if (!target) {
      var banner = form.querySelector('[data-section-error-banner]:not(.hidden)');
      if (banner) {
        banner.scrollIntoView({ behavior: 'smooth', block: 'center' });
        banner.setAttribute('tabindex', '-1');
        banner.focus({ preventScroll: true });
      }
      return;
    }
    if (target.disabled) target.disabled = false;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function showSaveIndicator(section) {
    var indicator = document.querySelector('[data-save-indicator="' + section + '"]');
    if (!indicator) return;
    indicator.classList.remove('hidden');
    window.setTimeout(function () {
      indicator.classList.add('hidden');
    }, 3000);
  }

  function submitSectionForm(form, options) {
    options = options || {};
    var section = form.getAttribute('data-section');
    var submitBtn = options.triggerBtn || form.querySelector('button[type="submit"]');
    var originalHtml =
      options.originalTriggerHtml !== undefined
        ? options.originalTriggerHtml
        : submitBtn
          ? submitBtn.innerHTML
          : '';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Saving…';
    }
    if (options.onStart) options.onStart();
    enableDisabledFields(form);
    var formData = new FormData(form);
    return fetch(form.getAttribute('action') || window.location.href, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: formData,
      credentials: 'same-origin',
    })
      .then(function (response) {
        return response.text().then(function (text) {
          var data = null;
          try {
            data = text ? JSON.parse(text) : null;
          } catch (parseErr) {
            data = { success: false, error: 'Unexpected server response.' };
          }
          return { ok: response.ok, data: data || { success: false } };
        });
      })
      .then(function (result) {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalHtml;
        }
        if (result.ok && result.data && result.data.success) {
          clearFieldErrors(form);
          showSaveIndicator(section);
          saveSectionSnapshot(section);
          markClean(section);
          if (options.onSuccess) options.onSuccess(result.data);
          return true;
        }
        clearFieldErrors(form);
        if (result.data && result.data.errors) {
          applyFieldErrors(form, result.data.errors);
          setTabStatus(section, 'error');
          window.requestAnimationFrame(function () {
            focusFirstFieldError(form);
          });
        } else if (result.data && result.data.error) {
          var banner = form.querySelector('[data-section-error-banner]');
          if (banner) {
            banner.classList.remove('hidden');
            banner.classList.add('flex');
            banner.setAttribute('role', 'alert');
            banner.innerHTML =
              '<p class="text-sm font-medium text-red-800">' + result.data.error + '</p>';
          }
          setTabStatus(section, 'error');
          window.requestAnimationFrame(function () {
            focusFirstFieldError(form);
          });
        }
        if (options.onError) options.onError(result.data);
        return false;
      })
      .catch(function () {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalHtml;
        }
        if (options.onError) options.onError(null);
        return false;
      });
  }

  function initForms() {
    document.querySelectorAll('form[data-section]').forEach(function (form) {
      var key = form.getAttribute('data-section');
      dirty[key] = false;
      form.addEventListener('input', function () {
        markDirty(key);
      });
      form.addEventListener('change', function () {
        markDirty(key);
      });
      if (form.getAttribute('data-section-save') === 'ajax') {
        form.addEventListener('submit', function (e) {
          e.preventDefault();
          submitSectionForm(form);
        });
      }
    });
  }

  function initTabs() {
    document.querySelectorAll('[data-tab]').forEach(function (tab) {
      tab.addEventListener('click', function (e) {
        var targetKey = tab.getAttribute('data-tab');
        var active = getActiveSection();
        if (active && dirty[active] && targetKey !== active) {
          e.preventDefault();
          promptLeave({ type: 'tab', target: targetKey });
          return;
        }
        switchToSection(targetKey, true);
      });
    });
  }

  function initModal() {
    var modal = document.getElementById('unsaved-changes-modal');
    if (!modal) return;

    var stayBtn = document.getElementById('unsaved-stay');
    var discardBtn = document.getElementById('unsaved-discard-switch');
    var saveBtn = document.getElementById('unsaved-save-switch');
    var backdrop = modal.querySelector('[data-unsaved-backdrop]');

    function closeModal() {
      hideUnsavedModal();
      clearPendingLeaveAction();
    }

    if (stayBtn) stayBtn.addEventListener('click', closeModal);
    if (backdrop) backdrop.addEventListener('click', closeModal);

    if (discardBtn) {
      discardBtn.addEventListener('click', completeLeaveAfterDiscard);
    }

    if (saveBtn && !saveBtn.getAttribute('data-default-html')) {
      saveBtn.setAttribute('data-default-html', saveBtn.innerHTML);
    }
    if (discardBtn && !discardBtn.getAttribute('data-default-html')) {
      discardBtn.setAttribute('data-default-html', discardBtn.innerHTML);
    }
    if (stayBtn && !stayBtn.getAttribute('data-default-html')) {
      stayBtn.setAttribute('data-default-html', stayBtn.innerHTML);
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var active = getActiveSection();
        var form = getFormForSection(active);
        if (!form) {
          completeLeaveAfterSave();
          return;
        }
        var originalSaveHtml = saveBtn.getAttribute('data-default-html') || saveBtn.innerHTML;
        setUnsavedModalStatus('Saving changes…', 'loading');
        setUnsavedModalButtonsDisabled(true);
        submitSectionForm(form, {
          triggerBtn: saveBtn,
          originalTriggerHtml: originalSaveHtml,
          onSuccess: function () {
            completeLeaveAfterSave();
          },
          onError: function () {
            hideUnsavedModal();
            clearPendingLeaveAction();
          },
        });
      });
    }
  }

  function isReloadShortcut(e) {
    if (e.key === 'F5') return true;
    if (!(e.ctrlKey || e.metaKey)) return false;
    if (e.key !== 'r' && e.key !== 'R') return false;
    return true;
  }

  function promptReloadLeave() {
    promptLeave({ type: 'reload' });
  }

  function initReloadGuard() {
    document.addEventListener('keydown', function (e) {
      if (!hasUnsavedChanges() || !isReloadShortcut(e)) return;
      e.preventDefault();
      promptReloadLeave();
    });
  }

  function initNavigationApiReloadGuard() {
    if (!window.navigation || typeof window.navigation.addEventListener !== 'function') return;
    window.navigation.addEventListener('navigate', function (e) {
      if (allowUnload || !hasUnsavedChanges() || e.navigationType !== 'reload') return;
      e.preventDefault();
      promptReloadLeave();
    });
  }

  function isSameDocumentNavigation(url) {
    return (
      url.origin === window.location.origin &&
      url.pathname === window.location.pathname &&
      url.search === window.location.search &&
      !!url.hash
    );
  }

  function shouldGuardLeaveLink(link) {
    if (!link || link.target === '_blank' || link.hasAttribute('download')) return false;
    var href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return false;
    try {
      return !isSameDocumentNavigation(new URL(link.href, window.location.href));
    } catch (err) {
      return false;
    }
  }

  function initNavigationGuard() {
    document.addEventListener(
      'click',
      function (e) {
        if (!hasUnsavedChanges()) return;
        var link = e.target.closest('a[href]');
        if (!shouldGuardLeaveLink(link)) return;
        e.preventDefault();
        promptLeave({ type: 'navigate', href: link.href });
      },
      true
    );
  }

  function initBeforeUnload() {
    window.addEventListener('beforeunload', function (e) {
      if (allowUnload || !hasUnsavedChanges()) return;
      e.preventDefault();
      e.returnValue = '';
      return e.returnValue;
    });
  }

  function boot() {
    initForms();
    initTabs();
    initModal();
    initReloadGuard();
    initNavigationApiReloadGuard();
    initNavigationGuard();
    initBeforeUnload();
    window.requestAnimationFrame(function () {
      document.querySelectorAll('form[data-section]').forEach(function (form) {
        saveSectionSnapshot(form.getAttribute('data-section'));
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.healthFormEdit = {
    submitSectionForm: submitSectionForm,
    switchToSection: switchToSection,
    getActiveSection: getActiveSection,
    markDirty: markDirty,
    markClean: markClean,
    discardSectionChanges: discardSectionChanges,
  };
})();
