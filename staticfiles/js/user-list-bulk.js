/**
 * User management bulk selection (Alpine + capture listener on bulk root).
 */
function userListBulk() {
  return {
    selected: {},
    selectedCount: 0,
    bulkAction: '',
    _bulkDeleteConfirmed: false,

    init() {
      this.syncSelectedFromDom();
      this._onChange = (event) => this.handleTableChange(event);
      this._onHtmxSwap = (event) => this.onTableSwapped(event);
      this.$el.addEventListener('change', this._onChange, true);
      document.body.addEventListener('htmx:afterSwap', this._onHtmxSwap);
    },

    rowCheckboxes() {
      const seen = new Set();
      const boxes = [];
      document
        .querySelectorAll('#user-table-container .js-bulk-select:not(:disabled)')
        .forEach((cb) => {
          if (seen.has(cb.value)) {
            return;
          }
          seen.add(cb.value);
          boxes.push(cb);
        });
      return boxes;
    },

    setCheckboxChecked(userId, checked) {
      document
        .querySelectorAll(`#user-table-container .js-bulk-select[value="${userId}"]`)
        .forEach((cb) => {
          cb.checked = checked;
        });
    },

    syncSelectedFromDom() {
      const next = {};
      this.rowCheckboxes().forEach((cb) => {
        if (cb.checked) {
          next[cb.value] = true;
        }
      });
      this.selected = next;
      this.selectedCount = Object.keys(next).length;
    },

    handleTableChange(event) {
      const target = event.target;
      if (!target || target.type !== 'checkbox') {
        return;
      }

      if (target.classList.contains('js-account-toggle')) {
        return;
      }

      if (target.classList.contains('js-bulk-select-all')) {
        this.toggleAll(target);
        return;
      }

      if (target.classList.contains('js-bulk-select')) {
        this.setCheckboxChecked(target.value, target.checked);
        this.syncSelectedFromDom();
        this.updateSelectAllState();
      }
    },

    toggleAll(master) {
      const shouldCheck = Boolean(master.checked);
      this.rowCheckboxes().forEach((cb) => {
        this.setCheckboxChecked(cb.value, shouldCheck);
      });
      this.syncSelectedFromDom();
      master.indeterminate = false;
    },

    updateSelectAllState() {
      const master = document.getElementById('select-all-users');
      const boxes = this.rowCheckboxes();
      if (!master) {
        return;
      }
      if (!boxes.length) {
        master.checked = false;
        master.indeterminate = false;
        return;
      }
      const checkedCount = boxes.filter((cb) => cb.checked).length;
      master.checked = checkedCount === boxes.length;
      master.indeterminate = checkedCount > 0 && checkedCount < boxes.length;
    },

    clearSelection() {
      this.selected = {};
      this.selectedCount = 0;
      this.bulkAction = '';
      document
        .querySelectorAll('#user-table-container .js-bulk-select')
        .forEach((cb) => {
          cb.checked = false;
        });
      const master = document.getElementById('select-all-users');
      if (master) {
        master.checked = false;
        master.indeterminate = false;
      }
    },

    selectedUserIds() {
      return Object.keys(this.selected);
    },

    syncBulkActionSelect(form) {
      const actionSelect = form?.querySelector('[name="action"]');
      if (actionSelect && this.bulkAction) {
        actionSelect.value = this.bulkAction;
      }
    },

    injectUserIdsIntoForm(form) {
      form.querySelectorAll('input.js-bulk-hidden-id').forEach((node) => node.remove());
      this.selectedUserIds().forEach((id) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'user_ids';
        input.value = id;
        input.className = 'js-bulk-hidden-id';
        form.appendChild(input);
      });
    },

    applyBulkRequestParameters(params) {
      this.syncSelectedFromDom();
      const ids = this.selectedUserIds();
      const action = this.bulkAction || params.action;
      if (action) {
        params.action = action;
      }
      if (ids.length) {
        params.user_ids = ids;
      }
    },

    onBulkConfigRequest(event) {
      const form = event.detail?.elt;
      if (!form || form.id !== 'user-bulk-form') {
        return;
      }
      this.applyBulkRequestParameters(event.detail.parameters);
    },

    onTableSwapped(event) {
      const target = event.detail?.target;
      if (!target || target.id !== 'user-table-container') {
        return;
      }
      this.clearSelection();
      this.$nextTick(() => this.updateSelectAllState());
    },

    onBulkRequest(event) {
      if (event.detail?.successful) {
        document.body.dispatchEvent(new CustomEvent('refreshUserStats'));
      }
    },

    beforeBulkSubmit(event) {
      if (!this.bulkAction) {
        event.preventDefault();
        return;
      }

      this.syncSelectedFromDom();

      if (this.selectedCount === 0) {
        event.preventDefault();
        window.alert('Select at least one user.');
        return;
      }

      if (
        this.bulkAction === 'delete'
        && !this._bulkDeleteConfirmed
        && !window.confirm(
          'Soft-delete the selected users? You can restore them from the Deleted page.',
        )
      ) {
        event.preventDefault();
        return;
      }
      this._bulkDeleteConfirmed = false;

      const form = event.target;
      this.syncBulkActionSelect(form);
      this.injectUserIdsIntoForm(form);
    },
  };
}
