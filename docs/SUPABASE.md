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

Migration `core.0023_enable_supabase_rls` (Postgres only) enables **RLS** on all `public` tables and revokes `anon` / `authenticated` access so PostgREST cannot read Django data. Django continues to use the `postgres` DB user and is unchanged. Re-run after manual schema work if needed:

```bash
python manage.py enable_supabase_rls
```

### 4. Copy academic catalog from SQLite (optional)

If colleges / courses / year levels exist in local `db.sqlite3` but not in Supabase yet:

```bash
# 1. Export from SQLite (works even when DATABASE_URL points at Supabase)
uv run python manage.py academic_catalog_transfer export --from-sqlite -o data/academic_catalog.json

# 2. Ensure Supabase schema is up to date
#    DATABASE_URL=postgresql://... in .env
uv run python manage.py migrate

# 3. Import into Postgres (add --clear to replace existing catalog rows)
uv run python manage.py academic_catalog_transfer import -i data/academic_catalog.json
```

The dump is name-keyed JSON (`data/academic_catalog.json`) so IDs can differ between SQLite and Postgres. Patient profile `department` / `course` / `year_level` text fields are unchanged by this command.

### 5. Migrate existing local media (optional)

If you have files under `media/` from SQLite + filesystem dev:

```bash
python manage.py migrate_media_to_supabase --dry-run
python manage.py migrate_media_to_supabase
```

## Production (hosted Supabase)

1. Create a Supabase project and link it in the dashboard.
2. Set `DATABASE_URL` and `SUPABASE_URL=https://[project-ref].supabase.co` in `.env` (never commit `.env`).

### Postgres connection modes

| Mode | Host pattern | Port | When to use |
|------|----------------|------|-------------|
| **Direct** | `db.[project-ref].supabase.co` | `5432` | IPv6-capable networks; simplest for local dev against hosted DB |
| **Session pooler** | `aws-0-[region]` or `aws-1-[region]` `.pooler.supabase.com` (user `postgres.[project-ref]`) | `5432` | **IPv4-only** networks (use if direct `db.*` fails DNS or is unreachable) |
| **Transaction pooler** | same pooler host | `6543` | Serverless / many short-lived connections (Django with `conn_max_age` is usually fine on session or direct) |

Example **direct** URL:

`postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres`

Example **session pooler** (IPv4-friendly, port 5432):

`postgresql://postgres.[project-ref]:[password]@aws-1-[region].pooler.supabase.com:5432/postgres` (or `aws-0-…` — copy from dashboard)

Example **transaction pooler** (port 6543):

`postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`

Copy the exact pooler host and region from **Supabase Dashboard → Project Settings → Database → Connection string**.

Django enables SSL for any non-local `DATABASE_URL` (`backend/settings.py`).

3. Set `USE_SUPABASE_STORAGE=True` with production S3 keys when using remote buckets.
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
| `could not translate host name` for `db.*.supabase.co` | Direct host is often **IPv6-only** (AAAA, no A record). Use **Session pooler** on port `5432` with user `postgres.[project-ref]`; host is `aws-0-[region]` or `aws-1-[region]` from **Connect → Session pooler** (not `db.*`) |
| Direct DB (`db.*.supabase.co:5432`) times out / no route | Same as above, or enable Supabase **IPv4 add-on** for direct access |
| Pooler: `Tenant or user not found` | Wrong **region** or pooler prefix (`aws-0` vs `aws-1`) — copy the full string from the dashboard |
| SSL / certificate errors to hosted Postgres | Ensure `DATABASE_URL` is not the local `127.0.0.1:54322` URL; remote URLs get `ssl_require` automatically |
| Upload fails with S3 error | Missing or wrong `SUPABASE_S3_*` keys; bucket not created |
| `SignatureDoesNotMatch` or `403` on `HeadObject` | **Hosted** projects must not use `SUPABASE_S3_REGION=local` — set your project's AWS region (e.g. `ap-southeast-1`, from Dashboard → Storage) or rely on pooler-host inference in `core/supabase_config.py` |
| `migrate_media_to_supabase` errors | `USE_SUPABASE_STORAGE=False` or credentials unset |
| Images 404 in dev without Supabase | Expected when `USE_SUPABASE_STORAGE=True`; files are in Storage, not `/media/` |
| Broken image icon / S3 URL 403–404 in browser | Supabase S3 presign URLs are not browser-safe; private files are served via `/storage/private/<path>` (authenticated proxy) |

## Security (Supabase linter / PostgREST)

Hosted projects run the [database linter](https://supabase.com/docs/guides/database/database-linter). Errors such as **RLS Disabled in Public** or **Sensitive Columns Exposed** mean tables in `public` are reachable via the Supabase API without row policies.

This app does **not** use PostgREST for app data—only Django ORM. After `migrate` on Postgres, ensure `0023_enable_supabase_rls` has been applied (or run `python manage.py enable_supabase_rls`). That enables RLS on every `public` table, adds an explicit **deny-all** policy (`jmcfi_deny_postgrest_access`) for `anon` / `authenticated`, and revokes direct grants. New tables get the same treatment via a Postgres event trigger. This clears linter errors for missing RLS and satisfies the informational “RLS enabled, no policy” check.

## Follow-ups (not implemented)

- **Channels / Redis**: Supabase does not provide Redis; use Upstash or self-hosted Redis for production WebSockets.
- **Supabase Auth**: Would replace `core/adapters.py`—deferred.
