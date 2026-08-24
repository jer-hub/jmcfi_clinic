/**
 * Shared analytics filter bar – Apply button + catalog cascading
 * (department required before program / year level, same as profile forms).
 */

function readAnalyticsFilterCatalog() {
  const catalog = window.__jmcfiAnalyticsFilterCatalog || {};
  return {
    config: catalog.config || {},
    colleges: catalog.colleges || [],
    coursesByCollege: catalog.coursesByCollege || {},
    yearLevelsByCollege: catalog.yearLevelsByCollege || {},
  };
}

function populateAcademicSelect(selectEl, placeholder, options, selected) {
  if (!selectEl) return;
  const opts = Array.isArray(options) ? options : [];
  const keep = (selected || '').trim();
  selectEl.innerHTML = '';
  const blank = document.createElement('option');
  blank.value = '';
  blank.textContent = placeholder;
  selectEl.appendChild(blank);
  opts.forEach((value) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = value;
    selectEl.appendChild(opt);
  });
  if (keep && !opts.includes(keep)) {
    const orphan = document.createElement('option');
    orphan.value = keep;
    orphan.textContent = keep;
    selectEl.appendChild(orphan);
  }
  selectEl.value = keep;
}

function lookupCatalogOptions(map, department) {
  if (!map || !department) return [];
  const direct = map[department];
  if (Array.isArray(direct) && direct.length) return direct;
  const normDept = String(department || '').trim().toLowerCase();
  const matchKey = Object.keys(map).find(
    (key) => String(key || '').trim().toLowerCase() === normDept,
  );
  return matchKey ? map[matchKey] || [] : [];
}

/**
 * Build cascade helpers as methods (not getters).
 * Object-spread of getters evaluates them once and freezes empty arrays.
 */
function buildAcademicCascade(config = {}, coursesByCollege = {}, yearLevelsByCollege = {}) {
  return {
    department: config.department || '',
    course: config.course || '',
    yearLevel: config.year_level || '',
    courseOptionsByCollege: coursesByCollege || {},
    yearLevelOptionsByCollege: yearLevelsByCollege || {},

    courseOptionsForDepartment() {
      if (!this.department) return [];
      return lookupCatalogOptions(this.courseOptionsByCollege, this.department);
    },

    yearLevelOptionsForDepartment() {
      if (!this.department) return [];
      return lookupCatalogOptions(this.yearLevelOptionsByCollege, this.department);
    },

    refreshDependentSelects() {
      const coursePlaceholder = this.department ? 'All programs' : 'Select college first';
      const yearPlaceholder = this.department ? 'All year levels' : 'Select college first';
      populateAcademicSelect(
        this.$refs.courseSelect,
        coursePlaceholder,
        this.courseOptionsForDepartment(),
        this.course,
      );
      populateAcademicSelect(
        this.$refs.yearLevelSelect,
        yearPlaceholder,
        this.yearLevelOptionsForDepartment(),
        this.yearLevel,
      );
    },

    syncModelsFromSelects() {
      if (this.$refs.departmentSelect) {
        this.department = this.$refs.departmentSelect.value;
      }
      if (this.$refs.courseSelect && this.$refs.courseSelect.options.length > 1) {
        this.course = this.$refs.courseSelect.value;
      }
      if (this.$refs.yearLevelSelect && this.$refs.yearLevelSelect.options.length > 1) {
        this.yearLevel = this.$refs.yearLevelSelect.value;
      }
    },

    onDepartmentChange() {
      this.department = this.$refs.departmentSelect
        ? this.$refs.departmentSelect.value
        : this.department;
      if (!this.department) {
        this.course = '';
        this.yearLevel = '';
      } else {
        const courses = this.courseOptionsForDepartment();
        const years = this.yearLevelOptionsForDepartment();
        if (this.course && !courses.includes(this.course)) {
          this.course = '';
        }
        if (this.yearLevel && !years.includes(this.yearLevel)) {
          this.yearLevel = '';
        }
      }
      this.refreshDependentSelects();
      this.syncModelsFromSelects();
    },

    onCourseChange() {
      this.course = this.$refs.courseSelect ? this.$refs.courseSelect.value : this.course;
    },

    onYearLevelChange() {
      this.yearLevel = this.$refs.yearLevelSelect
        ? this.$refs.yearLevelSelect.value
        : this.yearLevel;
    },
  };
}

function registerAnalyticsAlpineComponents() {
  if (!window.Alpine || window.__jmcfiAnalyticsAlpineRegistered) return;
  window.__jmcfiAnalyticsAlpineRegistered = true;

  Alpine.data('academicCascadeFields', () => {
    const { config, coursesByCollege, yearLevelsByCollege } = readAnalyticsFilterCatalog();
    const cascade = buildAcademicCascade(config, coursesByCollege, yearLevelsByCollege);
    return Object.assign(cascade, {
      init() {
        this.$nextTick(() => {
          this.refreshDependentSelects();
        });
      },
    });
  });

  Alpine.data('analyticsFilterBar', () => {
    const { config, colleges, coursesByCollege, yearLevelsByCollege } = readAnalyticsFilterCatalog();
    const cascade = buildAcademicCascade(config, coursesByCollege, yearLevelsByCollege);
    return Object.assign(cascade, {
      illnessCategory: config.illness_category || '',
      dateFrom: config.date_from || '',
      dateTo: config.date_to || '',
      selectedType: config.selected_type || '',
      collegeOptions: colleges || [],

      init() {
        this.syncOrphanDepartmentOption();
        this.$nextTick(() => {
          this.refreshDependentSelects();
        });
      },

      syncOrphanDepartmentOption() {
        const select = this.$refs.departmentSelect;
        if (!select || !this.department) return;
        const exists = Array.from(select.options).some((opt) => opt.value === this.department);
        if (!exists) {
          const opt = document.createElement('option');
          opt.value = this.department;
          opt.textContent = this.department;
          select.appendChild(opt);
        }
        select.value = this.department;
      },

      applyFilters() {
        this.syncModelsFromSelects();

        const params = new URLSearchParams(window.location.search);
        const filterKeys = [
          'date_from', 'date_to', 'department', 'course', 'year_level', 'illness_category', 'type',
        ];

        filterKeys.forEach((key) => params.delete(key));

        const setIf = (key, value) => {
          const trimmed = (value || '').trim();
          if (trimmed) params.set(key, trimmed);
        };

        setIf('date_from', this.dateFrom);
        setIf('date_to', this.dateTo);
        setIf('department', this.department);
        if (this.department) {
          setIf('course', this.course);
          setIf('year_level', this.yearLevel);
        }
        setIf('illness_category', this.illnessCategory);
        setIf('type', this.selectedType);

        const qs = params.toString();
        const next = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
        const current = `${window.location.pathname}${window.location.search}`;
        if (current !== next) {
          window.location.assign(next);
        }
      },
    });
  });
}

document.addEventListener('alpine:init', registerAnalyticsAlpineComponents);
// If this script loads after Alpine already started, register immediately.
if (window.Alpine) {
  registerAnalyticsAlpineComponents();
}
