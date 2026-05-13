# Vanilla JS → HTMX/Alpine.js Refactoring Roadmap

**Generated**: May 4, 2026  
**Total Violations**: 1,539 (1,095 errors, 444 warnings)  
**Priority**: High (requires comprehensive refactoring)

---

## Overview

The codebase heavily relies on vanilla JavaScript for DOM manipulation, event handling, and HTTP requests. This roadmap prioritizes refactoring by impact and effort.

### Statistics

| Metric | Count |
|--------|-------|
| **Total Violations** | 1,539 |
| **Critical Errors** | 1,095 |
| **Warnings** | 444 |
| **Affected Files** | 50+ |
| **Most Common Pattern** | `getElementById` (366) |

---

## Top 10 Problematic Patterns

| Pattern | Count | Severity | Fix |
|---------|-------|----------|-----|
| `getElementById()` | 366 | 🔴 | Use htmx targeting or Alpine.js x-ref |
| `classList` manipulation | 304 | 🟡 | Use Alpine.js :class binding |
| `addEventListener()` | 217 | 🔴 | Use htmx @click or hx-* attributes |
| `querySelector()` | 159 | 🔴 | Use htmx targeting or Alpine.js |
| `onclick` attributes | 125 | 🔴 | Use htmx or Alpine.js @click |
| `style` assignment | 79 | 🟡 | Use Alpine.js :style or Tailwind |
| `textContent` assignment | 78 | 🔴 | Use htmx or Alpine.js x-text |
| `innerHTML` assignment | 71 | 🔴 | Use htmx for server-driven updates |
| `setTimeout()` | 60 | 🟡 | Use htmx polling or Alpine watchers |
| `fetch()` | 50 | 🔴 | Use htmx hx-get/hx-post/hx-put |

---

## Files Requiring Refactoring (Priority Order)

### 🔴 CRITICAL (>70 violations each)

#### 1. Static JS Files (Highest Priority - Complete Rewrite)

- **[dental_chart.js](static/js/dental_chart.js)** — 123 violations
  - Heavy DOM manipulation
  - Canvas/chart rendering
  - Event listeners for tooth selection
  - **Effort**: High | **Impact**: High
  - **Strategy**: Extract chart logic into Alpine component, keep canvas rendering separate if needed

- **[admin/DateTimeShortcuts.js](static/admin/js/admin/DateTimeShortcuts.js)** — 45 violations
  - Django admin datetime picker
  - **Effort**: Medium | **Impact**: Medium
  - **Strategy**: Consider using Alpine.js wrapper or htmx integration

- **[actions.js](static/admin/js/actions.js)** — 33 violations
  - Django admin bulk actions
  - **Effort**: Medium | **Impact**: Low
  - **Strategy**: Integrate with htmx for admin form handling

- **[SelectFilter2.js](static/admin/js/SelectFilter2.js)** — 32 violations
  - Django admin select filtering
  - **Effort**: Low | **Impact**: Low
  - **Strategy**: Consider htmx-based filtering

#### 2. Template Files (High Priority - Systematic Refactoring)

- **[dental_record_edit.html](dental_records/templates/dental_records/dental_record_edit.html)** — 102 violations
  - Edit form with inline validation
  - **Effort**: High | **Impact**: High
  - **Strategy**: Convert form submission to htmx, use Alpine for state management

- **[dental_record_edit.html](core/templates/core/dental/dental_record_edit.html)** — 96 violations
  - Duplicate of above (different path)

- **[dental_record_form.html](dental_records/templates/dental_records/dental_record_form.html)** — 71 violations
  - Form with complex validation
  - **Effort**: Medium | **Impact**: High
  - **Strategy**: Use htmx for form submission, Alpine for field-level validation

- **[submit_feedback.html](feedback/templates/feedback/submit_feedback.html)** — 54 violations
  - Simple feedback form with notification
  - **Effort**: Low | **Impact**: Medium
  - **Strategy**: Quick win - convert to htmx form + Alpine toast

- **[schedule_appointment.html](core/templates/core/schedule_appointment.html)** — 45 violations
  - Appointment scheduling with date/time pickers
  - **Effort**: Medium | **Impact**: High
  - **Strategy**: htmx for submission, Alpine for date picker interaction

- **[base.html](core/templates/core/base.html)** — 42 violations
  - Navigation, modals, global behaviors
  - **Effort**: High | **Impact**: Very High
  - **Strategy**: Refactor layout infrastructure first, then cascade to child templates

- **[user_list.html](core/templates/core/user_management/user_list.html)** — 42 violations
  - User table with filters and bulk actions
  - **Effort**: Medium | **Impact**: High
  - **Strategy**: Convert table actions to htmx, use Alpine for filtering UI

### 🟡 HIGH (40-70 violations)

- [create_prescription.html](health_forms_services/templates/health_forms_services/create_prescription.html) — 43
- [edit_prescription_new.html](health_forms_services/templates/health_forms_services/edit_prescription_new.html) — 38
- [conversation_detail.html](messaging/templates/messaging/conversation_detail.html) — 35
- [edit_form.html](health_forms_services/templates/health_forms_services/edit_form.html) — 34
- [_base_edit.html](health_forms_services/templates/health_forms_services/_base_edit.html) — 34
- [inbox.html](messaging/templates/messaging/inbox.html) — 33
- [request_document.html](document_request/templates/document_request/request_document.html) — 24
- [schedule_appointment.html](appointments/templates/appointments/schedule_appointment.html) — 23

---

## Refactoring Phases

### Phase 1: Setup & Infrastructure (Week 1)

**Effort**: Low | **Blockers**: None

- [x] Create HTMX utilities module (`core/htmx_utils.py`)
- [x] Add HTMXMiddleware to settings
- [x] Create instruction files
- [ ] Update base.html with htmx/Alpine.js scripts
- [ ] Create reusable partial templates (modals, forms, messages)
- [ ] Update base.css for animation/transition support

**Tasks**:
```python
# settings.py - add middleware
MIDDLEWARE = [
    ...,
    'core.htmx_utils.HTMXMiddleware',
]
```

```html
<!-- templates/base.html -->
<script defer src="https://unpkg.com/htmx.org@1.9.10"></script>
<script defer src="https://unpkg.com/alpinejs@3.13.3"></script>
```

### Phase 2: Quick Wins (Weeks 2-3)

**Effort**: Low | **Impact**: High

1. **Feedback Form** ([submit_feedback.html](feedback/templates/feedback/submit_feedback.html))
   - Convert form to htmx POST
   - Replace setTimeout toast with Alpine.js transition
   - Estimated effort: 4 hours

2. **Static Admin Files** (DateTimeShortcuts, SelectFilter2)
   - Wrap with Alpine.js components
   - Consider deprecating in favor of built-in solutions
   - Estimated effort: 8 hours

3. **User List** ([user_list.html](core/templates/core/user_management/user_list.html))
   - Convert table actions to htmx DELETE
   - Use Alpine for filter UI
   - Estimated effort: 6 hours

### Phase 3: Core Features (Weeks 4-6)

**Effort**: High | **Impact**: Very High

1. **Appointment Scheduling** ([schedule_appointment.html](core/templates/core/schedule_appointment.html))
   - Convert form to htmx
   - Alpine.js date picker integration
   - Real-time availability checking via htmx polling
   - Estimated effort: 16 hours

2. **Health Forms** (prescription, form editing)
   - Convert all forms to htmx
   - Tab-based navigation with Alpine
   - Real-time field validation
   - Estimated effort: 24 hours

3. **Messaging** ([conversation_detail.html](messaging/templates/messaging/conversation_detail.html))
   - Replace WebSocket with htmx polling or keep WebSocket
   - Alpine for UI state (sidebar, typing indicator)
   - Estimated effort: 12 hours

### Phase 4: Dental Records (Weeks 7-9)

**Effort**: Very High | **Impact**: High

1. **Dental Chart** ([dental_chart.js](static/js/dental_chart.js))
   - Complex refactoring - likely keep Canvas/chart library
   - Wrap interaction layer in Alpine.js
   - Use htmx for tooth note CRUD
   - Estimated effort: 32 hours

2. **Dental Record Forms** (edit, form)
   - Convert forms to htmx
   - Use Alpine for tab switching
   - Estimated effort: 20 hours

### Phase 5: Base Layout & Infrastructure (Week 10)

**Effort**: High | **Blocker**: Do this last - cascades to all templates

1. **base.html** ([core/templates/core/base.html](core/templates/core/base.html))
   - Convert navigation to Alpine-driven
   - Convert modals to Alpine components
   - Global notification system via htmx
   - Estimated effort: 20 hours

---

## Implementation Guidelines

### When to Use Each Technology

| Scenario | Use | Example |
|----------|-----|---------|
| Form submission | **htmx** | POST task form → return task item |
| Modal toggle | **Alpine.js** | x-data: { open: false } → @click: open = !open |
| Table row deletion | **htmx** | hx-delete="/items/123" → return empty |
| Tab switching | **Alpine.js** | x-show & x-model for active tab |
| Search/filter | **htmx** | hx-get="/search?q=..." on input |
| Class management | **Alpine.js** | :class="{ active: tab === 1 }" |
| Date picker | **Alpine + htmx** | Alpine for UI, htmx for server validation |
| Charts/Canvas | **Keep vanilla JS** | But wrap interaction in Alpine |

### Testing Strategy

For each refactored feature:

1. **Unit Tests**: Test Django views with HTMX headers
2. **Integration Tests**: Test htmx requests return partial HTML
3. **E2E Tests**: Test full user workflows (if applicable)
4. **Regression Tests**: Ensure non-HTMX paths still work

Example:
```python
def test_create_task_htmx(self):
    response = self.client.post(
        '/tasks',
        {'title': 'Test'},
        HTTP_HX_REQUEST='true'
    )
    self.assertEqual(response.status_code, 201)
    self.assertContains(response, 'Test')
    self.assertNotContains(response, '<html>')
```

---

## Risk Mitigation

### Risks

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Breaking existing functionality | High | Maintain non-HTMX paths during refactoring |
| Performance regression | Medium | Profile htmx payload sizes, compare to fetch |
| Complexity increase | Medium | Keep htmx/Alpine code simple, document patterns |
| Browser compatibility | Low | Use modern browser targets |

### Rollback Strategy

- Keep old JavaScript files in version control until refactoring is complete
- Dual-path views (HTMX + direct navigation) during transition
- Feature flags for gradual rollout
- Simple revert to vanilla JS if needed

---

## Success Metrics

Track these metrics throughout refactoring:

| Metric | Target | Current |
|--------|--------|---------|
| Vanilla JS violations | 0 | 1,539 |
| JavaScript bundle size | < 50KB | TBD |
| Core Web Vitals (LCP) | < 2.5s | TBD |
| Form submission latency | < 200ms | TBD |
| Code coverage | > 80% | TBD |

---

## Quick Reference: Pattern Conversion Examples

### Example 1: Form Submission

**Before**:
```html
<form id="task-form">
  <input id="title" type="text">
  <button type="submit">Create</button>
</form>
<script>
  document.getElementById('task-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const res = await fetch('/tasks', { method: 'POST', body: new FormData(this) });
    const task = await res.json();
    // Update DOM...
  });
</script>
```

**After**:
```html
<form hx-post="/tasks" hx-target="#task-list" hx-swap="beforeend">
  <input name="title" type="text">
  <button type="submit">Create</button>
</form>
```

**View**:
```python
def create_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            return render(request, 'tasks/task_item.html', {'task': task}, status=201)
        return render(request, 'forms/task_form.html', {'form': form}, status=400)
```

### Example 2: Toggle

**Before**:
```html
<button onclick="toggleMenu()">Menu</button>
<nav id="menu" style="display: none;">...</nav>
<script>
  let open = false;
  function toggleMenu() {
    open = !open;
    document.getElementById('menu').style.display = open ? 'block' : 'none';
  }
</script>
```

**After**:
```html
<div x-data="{ menuOpen: false }">
  <button @click="menuOpen = !menuOpen">Menu</button>
  <nav x-show="menuOpen">...</nav>
</div>
```

---

## Resources

- [HTMX Documentation](https://htmx.org/)
- [Alpine.js Documentation](https://alpinejs.dev/)
- [Frontend Instruction](..../frontend-htmx-alpine.instructions.md)
- [Django HTMX Instruction](..../django-htmx-views.instructions.md)
- [Refactoring Guide](..../refactoring-vanilla-js.instructions.md)
- [HTMX Examples](https://htmx.org/examples/)

---

## Next Steps

1. **Approve refactoring roadmap** (this document)
2. **Set up infrastructure** (Phase 1)
3. **Start with quick wins** (Phase 2)
4. **Schedule reviews** at end of each phase
5. **Track progress** against metrics above
