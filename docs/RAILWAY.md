# Railway production deployment (JMCFI Clinic)

Deploy the Django/Channels app on [Railway](https://railway.com) using the repo **Dockerfile**. Postgres and file storage stay on **hosted Supabase**; Railway runs the web service and optional **Redis** for WebSockets.

## Architecture

| Component | Provider | Notes |
|-----------|----------|--------|
| Web + ASGI | Railway (Dockerfile → Daphne) | Binds to `$PORT` |
| Postgres | Supabase | `DATABASE_URL` pooler URL |
| Media uploads | Supabase Storage | `USE_SUPABASE_STORAGE=True` required |
| WebSockets / Channels | Railway Redis | Set `REDIS_URL` |
| Static assets | WhiteNoise | Built via `collectstatic` in Docker image |
| PDF certificates | wkhtmltopdf | Installed in Docker image |

## Prerequisites

1. GitHub repo connected to Railway
2. Hosted Supabase project ([`docs/SUPABASE.md`](SUPABASE.md))
3. Google OAuth credentials with production redirect URI
4. Railway CLI (optional): `npm i -g @railway/cli`

## 1. Create the Railway project

1. **New Project** → **Deploy from GitHub repo** → select `jmcfi_clinic`
2. Railway reads [`railway.json`](../railway.json):
   - Builder: **Dockerfile**
   - Pre-deploy: `python manage.py migrate --noinput`
   - Health check: `GET /health/`

## 2. Generate a public domain

In the web service → **Settings** → **Networking** → **Generate Domain**.

Railway sets `RAILWAY_PUBLIC_DOMAIN` (e.g. `your-app.up.railway.app`). The app auto-adds this to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

## 3. Add Redis (recommended)

1. **+ New** → **Database** → **Add Redis**
2. In the web service variables, set:
   ```env
   REDIS_URL=${{Redis.REDIS_URL}}
   ```
   (Replace `Redis` with your Redis service name if different.)

Without Redis, Channels falls back to in-memory layer (fine for a single replica; not for horizontal scaling).

## 4. Environment variables

Set these on the **web service** (never commit secrets):

| Variable | Example / source |
|----------|------------------|
| `SECRET_KEY` | Random 50+ char string |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.up.railway.app` |
| `CUSTOM_DOMAIN` | Optional custom hostname (no `https://`) |
| `DATABASE_URL` | Supabase pooler Postgres URL |
| `USE_SUPABASE_STORAGE` | `True` |
| `SUPABASE_URL` | `https://[ref].supabase.co` |
| `SUPABASE_S3_ACCESS_KEY_ID` | Supabase Storage S3 keys |
| `SUPABASE_S3_SECRET_ACCESS_KEY` | Supabase Storage S3 keys |
| `SUPABASE_STORAGE_BUCKET` | `clinic-private` |
| `SUPABASE_PUBLIC_STORAGE_BUCKET` | `clinic-public` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `GOOGLE_CLIENT_ID` | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console |
| `GOOGLE_ALLOWED_DOMAINS` | `jmc.edu.ph,jmcfi.edu.ph` |
| `WKHTMLTOPDF_CMD` | `/usr/bin/wkhtmltopdf` (default in Docker) |
| `EMAIL_BACKEND` | Production SMTP backend (optional) |

Railway injects automatically: `PORT`, `RAILWAY_PUBLIC_DOMAIN`, etc.

See [`.env.example`](../.env.example) for the full local/production template.

## 5. Google OAuth

In [Google Cloud Console](https://console.cloud.google.com/) → OAuth client → **Authorized redirect URIs**:

```text
https://your-app.up.railway.app/accounts/google/login/callback/
```

Add the same for any custom domain.

## 6. Custom domain (optional)

```bash
railway domain clinic.example.com
```

Follow Railway DNS instructions (CNAME + verification). Set:

```env
CUSTOM_DOMAIN=clinic.example.com
CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app,https://clinic.example.com
```

## 7. Deploy and verify

1. Push to `master` (or trigger manual deploy)
2. Watch build logs: `uv sync`, `collectstatic`, image start
3. Pre-deploy runs migrations against Supabase
4. Smoke test:
   - `GET https://your-app.up.railway.app/health/` → `{"status":"ok"}`
   - `GET https://your-app.up.railway.app/health/ready/` → database connected
   - Google login
   - Static JS/CSS load (WhiteNoise)
   - Messaging WebSocket (with Redis)
   - Issue a certificate PDF (wkhtmltopdf)

## Local Docker smoke test

```bash
docker build -t jmcfi-clinic .
docker run --rm -p 8000:8000 --env-file .env -e PORT=8000 -e DEBUG=False jmcfi-clinic
```

Open http://localhost:8000/health/

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `DisallowedHost` | `ALLOWED_HOSTS`, `RAILWAY_PUBLIC_DOMAIN`, custom domain |
| CSRF failures on login | `CSRF_TRUSTED_ORIGINS` includes `https://` origin |
| Redirect loop / HTTP issues | `DEBUG=False`; Railway terminates TLS at edge |
| Static 404 | Rebuild image; `collectstatic` runs in Dockerfile |
| WebSockets fail | `REDIS_URL` set; Daphne running (not gunicorn WSGI-only) |
| PDF generation fails | `WKHTMLTOPDF_CMD=/usr/bin/wkhtmltopdf`; use Docker image |
| DB connection errors | Supabase pooler URL; SSL enabled for remote hosts |

## Related docs

- [`docs/SUPABASE.md`](SUPABASE.md) — Postgres, storage, migrations
- [`README.md`](../README.md) — Local development
