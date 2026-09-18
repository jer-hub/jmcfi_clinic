# Cursor agents — docs vs rules vs skills

## What is tracked in git

| Location | Role |
|----------|------|
| `.cursor/rules/*.mdc` | **Source of truth** for clinic coding conventions (structure, views, templates, auth, UI) |
| `docs/` | Ops runbooks and this index |
| `*/…_POLICY.md` | Domain policy (roles, scheduling, documents, Google signup) |
| `README.md` | Human onboarding |

## What is local-only (gitignored)

| Location | Role |
|----------|------|
| `.cursor/skills/` | Optional design / UI packs (banner, brand, design-system, slides, ui-styling, ui-ux-pro-max). Not shared via git. |
| `.agents/skills/` | Optional agent modes (e.g. caveman). Not shared via git. |

Do **not** put clinic-wide conventions only in skills — they will not reach other machines. Put shared guidance in `.cursor/rules/` or `docs/`.

## Feedback UI (current)

- Use Django `messages` → inline banners (`templates/partials/messages.html`)
- Floating toasts / `showToast` / `user-toast` HX triggers are removed
- `htmx_add_toast()` remains as a **no-op** for older call sites; prefer `messages` + redirect / `HX-Redirect`

## CSS

- Tailwind CLI build: `npm run build:css` → `staticfiles/css/app.css`
- Do not reintroduce a Tailwind CDN in `base.html`

## When to use local design skills

If present under `.cursor/skills/`:

| Skill | Use for |
|-------|---------|
| `ui-ux-pro-max` | UX review, palettes, typography, stack-aware UI guidance |
| `ui-styling` | Tailwind / component styling work |
| `design` / `design-system` / `brand` | Brand systems, tokens, identity (non-app marketing) |
| `banner-design` / `slides` | Marketing banners and HTML decks |

For Django/HTMX clinic app work, prefer `.cursor/rules/` over design packs.
