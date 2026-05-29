/**
 * Admin analytics calendar heat map — tooltips on hover, in-page day panel on click.
 */
(function () {
  const BADGE_CLASSES = {
    success: 'bg-success-100 text-success-800',
    warning: 'bg-warning-100 text-warning-800',
    danger: 'bg-danger-100 text-danger-800',
    info: 'bg-info-100 text-info-800',
    primary: 'bg-primary-100 text-primary-800',
    draft: 'bg-gray-100 text-gray-700',
    muted: 'bg-muted-100 text-muted-700',
  };

  const TOOLTIP_WIDTH = 224;
  const TOOLTIP_EST_HEIGHT = 140;
  const VIEWPORT_PAD = 8;

  const MONTH_NAMES = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];

  function emptyDay(iso) {
    return {
      iso,
      label: iso,
      short_label: iso,
      appt_count: 0,
      doc_count: 0,
      count: 0,
      events: [],
      status_summary: [],
      list_url: '#',
      documents_url: '#',
      is_today: false,
    };
  }

  function scheduleSummary(day) {
    if (!day) {
      return 'Nothing scheduled';
    }
    const parts = [];
    const appts = day.appt_count || 0;
    const docs = day.doc_count || 0;
    if (appts) {
      parts.push(`${appts} appointment${appts === 1 ? '' : 's'}`);
    }
    if (docs) {
      parts.push(`${docs} document request${docs === 1 ? '' : 's'}`);
    }
    if (!parts.length) {
      return 'No appointments or document requests';
    }
    return parts.join(' · ');
  }

  function lastDayOfMonth(year, month) {
    return new Date(year, month, 0).getDate();
  }

  function selectedIsoForMonth(anchorIso, year, month) {
    const anchor = anchorIso ? new Date(`${anchorIso}T12:00:00`) : new Date();
    const day = Number.isNaN(anchor.getTime()) ? 1 : anchor.getDate();
    const lastDay = lastDayOfMonth(year, month);
    const d = Math.min(day, lastDay);
    const mm = String(month).padStart(2, '0');
    const dd = String(d).padStart(2, '0');
    return `${year}-${mm}-${dd}`;
  }

  function flattenWeeks(weeks) {
    if (!Array.isArray(weeks)) {
      return [];
    }
    return weeks.reduce((cells, week) => {
      if (Array.isArray(week)) {
        cells.push(...week);
      }
      return cells;
    }, []);
  }

  function readJsonScript(id) {
    const el = document.getElementById(id);
    if (!el || !el.textContent) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      console.error(`Failed to parse #${id}`, err);
      return null;
    }
  }

  function adminCalendarHeatmapData() {
    return {
      days: {},
      weeks: [],
      gridCells: [],
      year: 0,
      month: 0,
      monthLabel: '',
      fallbackMonthLabel: '',
      selectedIso: '',
      todayIso: '',
      monthApiUrl: '',
      monthLoading: false,
      tooltipIso: null,
      tooltipPlacement: 'above',
      tooltipTop: '0px',
      tooltipLeft: '0px',
      tooltipTransform: 'translate(-50%, -100%)',

      init() {
        const root = this.$root;
        this.monthApiUrl = root.dataset.monthApiUrl || '';
        this.todayIso = root.dataset.todayIso || '';
        this.fallbackMonthLabel = root.dataset.monthLabel || '';

        this.$nextTick(() => {
          this.loadInitialPayload();
        });
      },

      loadInitialPayload() {
        const root = this.$root;
        const payload = readJsonScript('admin-calendar-client-data');
        if (payload && typeof payload === 'object') {
          this.applyMonthPayload(payload);
          return;
        }

        const days = readJsonScript('admin-calendar-days-data');
        if (days && typeof days === 'object') {
          this.days = days;
        }

        const initial = root.dataset.initialIso || '';
        const fromUrl = new URLSearchParams(window.location.search).get('date');
        this.selectedIso = fromUrl || initial || this.todayIso;

        const year = parseInt(root.dataset.year, 10);
        const month = parseInt(root.dataset.month, 10);
        if (year && month) {
          this.year = year;
          this.month = month;
          this.monthLabel = this.fallbackMonthLabel || this.formatMonthLabel(year, month);
        }
      },

      displayMonthLabel() {
        return this.monthLabel || this.fallbackMonthLabel;
      },

      applyMonthPayload(payload) {
        if (!payload || typeof payload !== 'object') {
          return;
        }
        this.year = payload.year;
        this.month = payload.month;
        this.monthLabel = payload.monthLabel || this.formatMonthLabel(payload.year, payload.month);
        this.weeks = payload.weeks || [];
        this.gridCells = flattenWeeks(this.weeks);
        this.days = payload.days || {};
        this.selectedIso = payload.selectedIso || this.selectedIso;
        this.syncUrl();
      },

      formatMonthLabel(year, month) {
        const name = MONTH_NAMES[month - 1] || '';
        return `${name} ${year}`.trim();
      },

      selectedDay() {
        return this.days[this.selectedIso] || emptyDay(this.selectedIso);
      },

      tooltipDay() {
        if (!this.tooltipIso) {
          return null;
        }
        return this.days[this.tooltipIso] || emptyDay(this.tooltipIso);
      },

      scheduleSummary(day) {
        return scheduleSummary(day);
      },

      hasDayItems(day) {
        if (!day) {
          return false;
        }
        return Boolean((day.events && day.events.length) || day.appt_count || day.doc_count);
      },

      showTooltip(iso, event) {
        const target = event.currentTarget;
        if (!target || typeof target.getBoundingClientRect !== 'function') {
          return;
        }
        const rect = target.getBoundingClientRect();
        const half = TOOLTIP_WIDTH / 2;
        let left = rect.left + rect.width / 2;
        left = Math.max(
          VIEWPORT_PAD + half,
          Math.min(left, window.innerWidth - VIEWPORT_PAD - half),
        );

        const placeAbove = rect.top - VIEWPORT_PAD >= TOOLTIP_EST_HEIGHT;
        this.tooltipPlacement = placeAbove ? 'above' : 'below';
        this.tooltipTop = `${placeAbove ? rect.top - 10 : rect.bottom + 10}px`;
        this.tooltipLeft = `${left}px`;
        this.tooltipTransform = placeAbove
          ? 'translate(-50%, -100%)'
          : 'translate(-50%, 0)';
        this.tooltipIso = iso;
      },

      hideTooltip() {
        this.tooltipIso = null;
      },

      onCellLeave(event) {
        const cell = event.currentTarget;
        const next = event.relatedTarget;
        if (next && cell.contains(next)) {
          return;
        }
        this.hideTooltip();
      },

      onGridFocusOut(event) {
        const grid = event.currentTarget;
        if (grid && event.relatedTarget && grid.contains(event.relatedTarget)) {
          return;
        }
        this.hideTooltip();
      },

      selectDay(iso) {
        this.selectedIso = iso;
        this.hideTooltip();
        this.syncUrl();
      },

      syncUrl() {
        if (!this.year || !this.month || !this.selectedIso) {
          return;
        }
        const url = new URL(window.location.href);
        url.searchParams.set('year', String(this.year));
        url.searchParams.set('month', String(this.month));
        url.searchParams.set('date', this.selectedIso);
        window.history.replaceState({}, '', url);
      },

      isSelected(iso) {
        return this.selectedIso === iso;
      },

      isToday(iso) {
        return iso === this.todayIso;
      },

      dayButtonClasses(iso, heatClass) {
        const base =
          'flex flex-col items-center justify-center flex-1 rounded-md transition-colors min-h-[2.75rem] w-full focus:outline-none';
        const selected = this.isSelected(iso);
        const today = this.isToday(iso);
        let classes = base;

        if (heatClass) {
          classes += ` ${heatClass}`;
        } else if (!selected) {
          classes += ' hover:bg-gray-50';
        }

        if (selected) {
          classes += ' ring-2 ring-inset ring-primary-500 font-bold z-[1]';
        } else {
          classes +=
            ' focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-500';
          if (today) {
            classes += ' ring-1 ring-inset ring-primary-300';
          }
        }

        return classes;
      },

      dayAriaLabel(cell) {
        const day = this.days[cell.iso] || emptyDay(cell.iso);
        const parts = [day.label];
        const appts = cell.event_count || day.appt_count || 0;
        const docs = cell.document_count || day.doc_count || 0;
        if (appts) {
          parts.push(`${appts} appointment${appts === 1 ? '' : 's'}`);
        }
        if (docs) {
          parts.push(`${docs} document request${docs === 1 ? '' : 's'}`);
        }
        return parts.join(' — ');
      },

      async changeMonth(delta) {
        if (this.monthLoading || !this.monthApiUrl) {
          return;
        }
        let year = this.year;
        let month = this.month + delta;
        if (month < 1) {
          month = 12;
          year -= 1;
        } else if (month > 12) {
          month = 1;
          year += 1;
        }
        const selectedIso = selectedIsoForMonth(this.selectedIso, year, month);
        await this.loadMonth(year, month, selectedIso);
      },

      async loadMonth(year, month, selectedIso) {
        if (!this.monthApiUrl) {
          return;
        }
        this.monthLoading = true;
        this.hideTooltip();
        try {
          const url = new URL(this.monthApiUrl, window.location.origin);
          url.searchParams.set('year', String(year));
          url.searchParams.set('month', String(month));
          if (selectedIso) {
            url.searchParams.set('date', selectedIso);
          }
          const response = await fetch(url, {
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
          });
          if (!response.ok) {
            return;
          }
          const payload = await response.json();
          this.applyMonthPayload(payload);
        } finally {
          this.monthLoading = false;
        }
      },

      badgeClasses(variant) {
        return `inline-flex items-center gap-1 rounded-full font-medium px-2 py-0.5 text-xs ${
          BADGE_CLASSES[variant] || BADGE_CLASSES.muted
        }`;
      },

      eventCardClasses(event) {
        if (event.event_kind === 'document') {
          return 'border-info-200 bg-info-50/40 hover:border-info-300 hover:bg-info-50/70';
        }
        if (event.is_cancelled) {
          return 'border-dashed border-gray-300 bg-gray-50/90 hover:bg-gray-100/90';
        }
        if (event.is_completed) {
          return 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50/80';
        }
        return 'border-gray-200 bg-white hover:border-primary-200 hover:bg-primary-50/50 hover:shadow-sm';
      },

      eventTimeClasses(event) {
        if (event.event_kind === 'document') {
          return 'bg-info-50 text-info-900 border-info-100';
        }
        const map = {
          warning: 'bg-warning-50 text-warning-900 border-warning-100',
          success: 'bg-success-50 text-success-900 border-success-100',
          danger: 'bg-danger-50/80 text-danger-800 border-danger-100',
        };
        return map[event.variant] || 'bg-muted-50 text-muted-800 border-muted-100';
      },
    };
  }

  document.addEventListener('alpine:init', () => {
    Alpine.data('adminCalendarHeatmap', adminCalendarHeatmapData);
  });

  window.adminCalendarHeatmap = adminCalendarHeatmapData;
})();
