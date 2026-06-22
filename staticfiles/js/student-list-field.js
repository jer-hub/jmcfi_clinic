/**
 * Alpine data factory for tag-style allergies / medical-conditions inputs.
 */
(function () {
  window.__hfListFields = window.__hfListFields || {};
  window.__hfPendingListFieldValues = window.__hfPendingListFieldValues || {};

  function parseListValue(value) {
    return (value || '')
      .split(/[\r\n,;]+/)
      .map((item) => item.trim())
      .filter((item, index, items) => item && items.indexOf(item) === index);
  }

  function studentListFieldFactory(initialValue) {
    return {
      listItems: [],
      listInput: '',
      validationError: '',
      serializedValue: initialValue || '',

      init() {
        const fieldName = this.$el.dataset.listField;
        if (fieldName) {
          window.__hfListFields[fieldName] = this;
        }
        this.reloadFromValue(this.serializedValue);
        if (fieldName && Object.prototype.hasOwnProperty.call(window.__hfPendingListFieldValues, fieldName)) {
          this.reloadFromValue(window.__hfPendingListFieldValues[fieldName]);
          delete window.__hfPendingListFieldValues[fieldName];
        }
        this.$el.addEventListener('hf:list-field-prefill', (event) => {
          this.reloadFromValue(event.detail?.value ?? '');
        });
      },

      syncValue() {
        this.serializedValue = this.listItems.join('\n');
      },

      addItem() {
        const item = (this.listInput || '').trim();
        if (!item) return;
        if (item.length > 120) {
          this.validationError = 'Each item must be 120 characters or fewer.';
          return;
        }

        if (!this.listItems.includes(item)) {
          this.listItems.push(item);
        }

        this.listInput = '';
        this.validationError = '';
        this.syncValue();
      },

      removeItem(index) {
        this.listItems.splice(index, 1);
        this.syncValue();
      },

      reloadFromValue(value) {
        this.serializedValue = value || '';
        this.listInput = '';
        this.validationError = '';
        this.listItems = parseListValue(this.serializedValue);
        this.syncValue();
      },
    };
  }

  window.studentListField = studentListFieldFactory;
  window.hfIsListField = function hfIsListField(fieldName) {
    return Boolean(
      window.__hfListFields[fieldName] ||
      document.querySelector(`[data-list-field="${fieldName}"]`),
    );
  };

  window.hfReloadListField = function hfReloadListField(fieldName, value) {
    if (!window.hfIsListField(fieldName)) {
      return false;
    }

    const nextValue = value || '';
    const component = window.__hfListFields[fieldName];
    if (component && typeof component.reloadFromValue === 'function') {
      component.reloadFromValue(nextValue);
      return true;
    }

    window.__hfPendingListFieldValues[fieldName] = nextValue;
    const listRoot = document.querySelector(`[data-list-field="${fieldName}"]`);
    if (listRoot) {
      listRoot.dispatchEvent(
        new CustomEvent('hf:list-field-prefill', {
          bubbles: false,
          detail: { value: nextValue },
        }),
      );
    }
    return true;
  };

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('studentListField', studentListFieldFactory);
  });
})();
