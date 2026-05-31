# Supabase setup (JMCFI Clinic)

JMCFI Clinic can use **Supabase Postgres** and **Supabase Storage** for local development and production. Google OAuth, Django sessions, and Channels are unchanged.

## What Supabase provides

| Component | Env vars | Notes |
|-----------|----------|--------|
| Postgres | `DATABASE_URL` | Django migrations own all app tables |
| Storage (S3 API) | `USE_SUPABASE_STORAGE`, `SUPABASE_*` | Private bucket `clinic-private` for PHI uploads |

Out of scope: Supabase Auth (keep django-allauth), Supabase Realtime (keep Channels; use Redis in production if needed).

## Prerequisites

1. [Supabase CLI](https://supabase.com/docs/guides/cli) installed
2. [uv](https://github.com/astral-sh/uv) for Python dependencies
3. Google OAuth vars in `.env` (see root `.env.example`)

## Local setup

### 1. Start Supabase

From the repository root:

```bash
supabase start
supabase status
```

Note the **DB URL** (port `54322`) and **API URL** (port `54321`).

### 2. Configure Django

```bash
cp .env.example .env
```

Set at minimum:

```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
SUPABASE_URL=http://127.0.0.1:54321
```

Create **S3 access keys** in Supabase Studio → Project Settings → Storage (or your hosted project dashboard), then:

```env
USE_SUPABASE_STORAGE=True
SUPABASE_STORAGE_BUCKET=clinic-private
SUPABASE_S3_ACCESS_KEY_ID=<from dashboard>
SUPABASE_S3_SECRET_ACCESS_KEY=<from dashboard>
```

### 3. Apply storage buckets

Bucket seed SQL lives in `supabase/migrations/20260531000000_storage_buckets.sql`. Apply with:

```bash
supabase db reset
```

Or run migrations only: `supabase migration up`.

Django schema is **not** managed by Supabase SQL—run:

```bash
uv sync
python manage.py migrate
python manage.py runserver
```

### 4. Migrate existing local media (optional)

If you have files under `media/` from SQLite + filesystem dev:

```bash
python manage.py migrate_media_to_supabase --dry-run
python manage.py migrate_media_to_supabase
```

## Production (hosted Supabase)

1. Create a Supabase project and link it in the dashboard.
2. Use the **connection pooler** URL (transaction mode, port `6543`) for `DATABASE_URL` in production, e.g.:

   `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`

3. Set `USE_SUPABASE_STORAGE=True` with production S3 keys and `SUPABASE_URL=https://[project-ref].supabase.co`.
4. Do **not** serve `/media/` from Django when storage is remote (`backend/urls.py` already guards this).

## Tests and CI

`python manage.py test` uses **SQLite** and **local filesystem storage** unless you set `TEST_DATABASE_URL`.

No `supabase start` is required for the default test suite.

To run tests against Postgres:

```env
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `connection refused` on port 54322 | Run `supabase start` or fix `DATABASE_URL` |
| Upload fails with S3 error | Missing or wrong `SUPABASE_S3_*` keys; bucket not created |
| `migrate_media_to_supabase` errors | `USE_SUPABASE_STORAGE=False` or credentials unset |
| Images 404 in dev without Supabase | Expected when `USE_SUPABASE_STORAGE=True`; files are in Storage, not `/media/` |

## Follow-ups (not implemented)

- **Channels / Redis**: Supabase does not provide Redis; use Upstash or self-hosted Redis for production WebSockets.
- **Row Level Security**: Optional if exposing PostgREST; Django uses direct DB credentials today.
- **Supabase Auth**: Would replace `core/adapters.py`—deferred.
