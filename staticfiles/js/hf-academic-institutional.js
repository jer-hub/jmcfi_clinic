/**
 * Alpine component for institutional department/college search picker.
 * Requires window.__jmcfiAcademicCatalog = { colleges, coursesByCollege, yearLevelsByCollege }.
 */
function hfAcademicInstitutionalSection(initial = {}) {
  const catalog = window.__jmcfiAcademicCatalog || {};
  return {
    department: initial.department || '',
    course: initial.course || '',
    yearLevel: initial.yearLevel || '',
    designation: (initial.designation || 'student').toLowerCase(),
    departmentQuery: '',
    departmentOpen: false,
    departmentHighlight: 0,
    collegeOptions: catalog.colleges || [],
    courseOptionsByCollege: catalog.coursesByCollege || {},
    yearLevelOptionsByCollege: catalog.yearLevelsByCollege || {},

    normalizeDepartment(value) {
      const raw = String(value || '').trim();
      if (!raw) return '';
      if (this.collegeOptions.includes(raw)) return raw;
      const parts = raw.split(' - ');
      const tail = parts[parts.length - 1]?.trim() || '';
      if (tail && this.collegeOptions.includes(tail)) return tail;
      return raw;
    },

    isStudentDesignation() {
      return (this.designation || '').toLowerCase() === 'student';
    },

    isEmployeeDesignation() {
      return (this.designation || '').toLowerCase() === 'employee';
    },

    isGuestDesignation() {
      return ((this.designation || '').toLowerCase() === 'guest');
    },

    init() {
      const live = window.__jmcfiAcademicCatalog || {};
      this.collegeOptions = live.colleges || this.collegeOptions;
      this.courseOptionsByCollege = live.coursesByCollege || this.courseOptionsByCollege;
      this.yearLevelOptionsByCollege = live.yearLevelsByCollege || this.yearLevelOptionsByCollege;

      const deptInput = this.$root.querySelector('#id_department_college_office');
      const designationSelect = this.$root.querySelector('#id_designation');
      const courseSelect = this.$refs.courseSelect;
      const yearSelect = this.$refs.yearLevelSelect;

      if (designationSelect && !this.designation) {
        this.designation = (designationSelect.value || 'student').toLowerCase();
      }
      this.$watch('designation', (value) => {
        if ((value || '').toLowerCase() === 'employee') {
          this.course = '';
          this.yearLevel = '';
          if (courseSelect) courseSelect.value = '';
          if (yearSelect) yearSelect.value = '';
        }
        this.refreshDependentSelects({ clearInvalid: false });
      });

      const deptRaw = (
        this.department
        || deptInput?.dataset?.initialValue
        || deptInput?.getAttribute?.('value')
        || deptInput?.value
        || ''
      ).trim();
      this.department = this.normalizeDepartment(deptRaw);
      if (deptInput) deptInput.value = this.department;

      this.course = (
        this.course
        || courseSelect?.dataset?.prefillValue
        || courseSelect?.value
        || ''
      ).trim();
      this.yearLevel = (
        this.yearLevel
        || yearSelect?.dataset?.prefillValue
        || yearSelect?.value
        || ''
      ).trim();

      this.departmentQuery = this.department;
      this._suppressDeptWatch = false;
      this.$watch('department', () => {
        if (this._suppressDeptWatch) return;
        this.onDepartmentChange();
      });
      if (deptInput) {
        const onExternal = () => this.syncFromExternalPrefill();
        deptInput.addEventListener('input', onExternal);
        deptInput.addEventListener('change', onExternal);
      }
      this.$nextTick(() => this.refreshDependentSelects({ clearInvalid: false }));
    },

    syncFromExternalPrefill() {
      const deptInput = this.$root.querySelector('#id_department_college_office');
      const courseSelect = this.$refs.courseSelect;
      const yearSelect = this.$refs.yearLevelSelect;
      this._suppressDeptWatch = true;
      this.department = this.normalizeDepartment(
        (deptInput?.value || deptInput?.dataset?.initialValue || '').trim(),
      );
      this.departmentQuery = this.department;
      this.course = (
        courseSelect?.dataset?.prefillValue
        || courseSelect?.value
        || this.course
        || ''
      ).trim();
      this.yearLevel = (
        yearSelect?.dataset?.prefillValue
        || yearSelect?.value
        || this.yearLevel
        || ''
      ).trim();
      this.refreshDependentSelects({ clearInvalid: false });
      this._suppressDeptWatch = false;
    },

    get filteredCollegeOptions() {
      const q = (this.departmentQuery || '').trim().toLowerCase();
      if (!q) return this.collegeOptions;
      return this.collegeOptions.filter((name) => String(name).toLowerCase().includes(q));
    },

    get departmentInitial() {
      return this.collegeInitial(this.department);
    },

    collegeInitial(name) {
      const text = String(name || '').trim();
      if (!text) return '?';
      const words = text.split(/\s+/).filter(Boolean);
      if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
      return text.slice(0, 2).toUpperCase();
    },

    openDepartmentDropdown() {
      this.departmentOpen = true;
      const options = this.filteredCollegeOptions;
      const selectedIdx = this.department ? options.indexOf(this.department) : -1;
      this.departmentHighlight = selectedIdx >= 0 ? selectedIdx : 0;
      this.$nextTick(() => this.scrollHighlightedDepartmentIntoView());
    },

    startDepartmentSearch() {
      this.departmentQuery = '';
      this.openDepartmentDropdown();
      this.$nextTick(() => this.$refs.departmentSearch?.focus());
    },

    onDepartmentQueryInput() {
      this.departmentOpen = true;
      this.departmentHighlight = 0;
      this.$nextTick(() => this.scrollHighlightedDepartmentIntoView());
    },

    closeDepartmentDropdown() {
      this.departmentOpen = false;
      this.departmentQuery = this.department || '';
    },

    selectDepartment(option) {
      this.department = option || '';
      this.departmentQuery = this.department;
      this.departmentOpen = false;
      this.onDepartmentChange();
    },

    clearDepartment() {
      this.department = '';
      this.departmentQuery = '';
      this.departmentOpen = true;
      this.departmentHighlight = 0;
      this.onDepartmentChange();
      this.$nextTick(() => this.$refs.departmentSearch?.focus());
    },

    scrollHighlightedDepartmentIntoView() {
      const list = this.$refs.departmentList;
      if (!list) return;
      const el = list.querySelector(`[data-dept-idx="${this.departmentHighlight}"]`);
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ block: 'nearest' });
      }
    },

    highlightNextDepartment() {
      const len = this.filteredCollegeOptions.length;
      if (!len) return;
      if (!this.departmentOpen) this.openDepartmentDropdown();
      this.departmentHighlight = (this.departmentHighlight + 1) % len;
      this.$nextTick(() => this.scrollHighlightedDepartmentIntoView());
    },

    highlightPrevDepartment() {
      const len = this.filteredCollegeOptions.length;
      if (!len) return;
      if (!this.departmentOpen) this.openDepartmentDropdown();
      this.departmentHighlight = (this.departmentHighlight - 1 + len) % len;
      this.$nextTick(() => this.scrollHighlightedDepartmentIntoView());
    },

    selectHighlightedDepartment() {
      const options = this.filteredCollegeOptions;
      if (!options.length) return;
      const idx = Math.min(Math.max(this.departmentHighlight, 0), options.length - 1);
      this.selectDepartment(options[idx]);
    },

    get filteredCourseOptions() {
      return this.courseOptionsByCollege[this.department] || [];
    },

    get filteredYearLevelOptions() {
      return this.yearLevelOptionsByCollege[this.department] || [];
    },

    populateSelect(selectEl, placeholder, options, selected) {
      if (!selectEl) return;
      const prefilled = selectEl.dataset.prefillValue || '';
      const preferred = selected || prefilled;
      const hasPreferred = preferred && options.includes(preferred);
      const keep = hasPreferred ? preferred : (preferred || '');
      selectEl.innerHTML = '';
      const blank = document.createElement('option');
      blank.value = '';
      blank.textContent = placeholder;
      selectEl.appendChild(blank);
      options.forEach((value) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        selectEl.appendChild(opt);
      });
      if (preferred && !hasPreferred) {
        const legacy = document.createElement('option');
        legacy.value = preferred;
        legacy.textContent = `${preferred} (existing)`;
        selectEl.appendChild(legacy);
      }
      selectEl.value = keep;
      if (keep && selectEl.dataset.prefillValue) {
        delete selectEl.dataset.prefillValue;
      }
    },

    refreshDependentSelects({ clearInvalid = false } = {}) {
      if (clearInvalid) {
        if (this.course && !this.filteredCourseOptions.includes(this.course)) {
          this.course = '';
        }
        if (this.yearLevel && !this.filteredYearLevelOptions.includes(this.yearLevel)) {
          this.yearLevel = '';
        }
      }
      this.populateSelect(this.$refs.courseSelect, 'Select course/program', this.filteredCourseOptions, this.course);
      this.populateSelect(this.$refs.yearLevelSelect, 'Select year level', this.filteredYearLevelOptions, this.yearLevel);
      this.course = this.$refs.courseSelect ? this.$refs.courseSelect.value : this.course;
      this.yearLevel = this.$refs.yearLevelSelect ? this.$refs.yearLevelSelect.value : this.yearLevel;
    },

    onDepartmentChange() {
      this.refreshDependentSelects({ clearInvalid: true });
    },

    isGuestDesignation() {
      return ((this.designation || '').toLowerCase() === 'guest');
    },
  };
}
