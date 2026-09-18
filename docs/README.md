# Documentation index

Tracked project docs. Agent coding conventions live in [`.cursor/rules/`](../.cursor/rules/); see [CURSOR.md](CURSOR.md) for how docs, rules, and local skills fit together.

## Ops & deploy

| Doc | Purpose |
|-----|---------|
| [SUPABASE.md](SUPABASE.md) | Local Supabase CLI, Postgres (`DATABASE_URL`), Storage |
| [DIGITALOCEAN.md](DIGITALOCEAN.md) | DigitalOcean App Platform production runbook |

## Domain policies (in-app)

| Doc | Purpose |
|-----|---------|
| [`core/ADMIN_ROLE_POLICY.md`](../core/ADMIN_ROLE_POLICY.md) | Admin access boundaries |
| [`core/GOOGLE_STUDENT_PROFILE_POLICY.md`](../core/GOOGLE_STUDENT_PROFILE_POLICY.md) | Patient profile completion on Google signup |
| [`appointments/APPOINTMENT_SCHEDULING_POLICY.md`](../appointments/APPOINTMENT_SCHEDULING_POLICY.md) | Scheduling rules |
| [`document_request/DOCUMENT_REQUEST_POLICY.md`](../document_request/DOCUMENT_REQUEST_POLICY.md) | Document request workflow |

## Quick pointers

- Stack & app map → `.cursor/rules/project-structure.mdc`
- Views / HTMX responses → `.cursor/rules/django-views.mdc`
- Templates & messages → `.cursor/rules/template-conventions.mdc`
- UI consistency (no floating toasts) → `.cursor/rules/ui-consistency.mdc`
- Frontend (HTMX + Alpine) → `.cursor/rules/frontend-htmx-alpine.mdc`
