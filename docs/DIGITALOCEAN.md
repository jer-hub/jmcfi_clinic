# DigitalOcean App Platform Deployment

This runbook deploys JMCFI Clinic to DigitalOcean App Platform while keeping Supabase for database and file storage.

## 1) Prerequisites

- Supabase project with Postgres + Storage configured
- Google OAuth credentials configured for production callback
- GitHub repository connected to DigitalOcean App Platform

## 2) Create App Platform resources

1. Create a new App in DigitalOcean App Platform from this repository.
2. Choose **Dockerfile** as the build strategy (not Python buildpack auto-detect).
3. Set **Dockerfile path** to `Dockerfile`.
4. Add one **Web Service** component.
5. Add one **Managed Redis** component and copy its connection string.

If App Platform still detects a Python buildpack, upload [`.do/app.yaml`](../.do/app.yaml) in **Settings → App Spec** so `dockerfile_path` and `run_command` are explicit.

## 3) Web service configuration

- **HTTP Port**: `8080`
- **Health Check Path**: `/health/`
- **Health Check Initial Delay**: `30` seconds (recommended on first deploy)
- **Build Command**: leave empty (handled by `Dockerfile`)
- **Run Command**: `bash scripts/start.sh`
  - If you use Dockerfile correctly, this can also be left empty because `Dockerfile` sets `CMD`.
  - Do **not** leave a blank Run Command override in the UI; an empty override can replace the Dockerfile `CMD` and cause:
    `failed to launch: determine start command: when there is no default process a command is required`
- **Instance count**: start with 1, scale as needed

## 4) Environment variables

Set these in the App Platform web service:

- `DEBUG=False`
- `SECRET_KEY=<strong-random-secret>`
- `ALLOWED_HOSTS=<your-app-xxxxxx>.ondigitalocean.app` (full hostname; optional `.ondigitalocean.app` for all DO subdomains — never `*.ondigitalocean.app`)
- `CSRF_TRUSTED_ORIGINS=https://<your-app-xxxxxx>.ondigitalocean.app,https://<custom-domain-if-any>`
- `APP_DOMAIN=<your-app-xxxxxx>.ondigitalocean.app` (concrete hostname from the DO app URL, not a wildcard)
- `CUSTOM_DOMAIN=<custom-domain-if-any>`
- `DATABASE_URL=<supabase-postgres-url>`
- `USE_SUPABASE_STORAGE=True`
- `SUPABASE_URL=<https://project-ref.supabase.co>`
- `SUPABASE_STORAGE_BUCKET=clinic-private`
- `SUPABASE_PUBLIC_STORAGE_BUCKET=clinic-public`
- `SUPABASE_S3_ACCESS_KEY_ID=<supabase-s3-key>`
- `SUPABASE_S3_SECRET_ACCESS_KEY=<supabase-s3-secret>`
- `SUPABASE_S3_REGION=<supabase-region>`
- `REDIS_URL=<digitalocean-managed-redis-url>`
- `GOOGLE_CLIENT_ID=<google-client-id>`
- `GOOGLE_CLIENT_SECRET=<google-client-secret>`
- `GOOGLE_ALLOWED_DOMAINS=<comma-separated-allowed-domains>`

## 5) Release command

Configure App Platform to run database migrations on deploy:

```bash
python manage.py migrate --noinput
```

## 6) Pre-deploy verification

Run locally before pushing:

```bash
python manage.py check
python manage.py test core.tests_digitalocean_settings
python manage.py collectstatic --noinput
```

## 7) Post-deploy smoke tests

- `GET /health/` returns 200
- `GET /health/ready/` returns 200
- static assets load without 404 in login/dashboard pages
- Google OAuth login callback succeeds
- messaging WebSocket flow works with Redis-backed Channels
- file upload and read works through Supabase storage

## 8) Rollback basics

- Use App Platform deploy history to rollback to the previous successful revision.
- If schema migration caused issues, restore from Supabase backup and redeploy previous app revision.

## 9) Troubleshooting deploy errors

### `when there is no default process a command is required`

Cause: App Platform is using a Python buildpack without a start command (no `Procfile`/run command), instead of the Docker image.

Fix:

1. Open the app → **Settings** → select the **web** component.
2. Confirm **Source** uses **Dockerfile** (`Dockerfile`), not buildpack auto-detect.
3. Set **Run Command** to:
   ```bash
   bash scripts/start.sh
   ```
4. Clear any blank/whitespace run command override if present.
5. Redeploy.

### `Readiness probe failed ... connection refused on :8080`

Cause: the web process never started (usually the error above), or the HTTP port mismatch.

Fix:

1. Apply the run-command/Dockerfile fixes above.
2. Set **HTTP Port** to `8080`.
3. Set health check path to `/health/`.
4. Increase health check initial delay to `30` seconds.
5. Verify required runtime env vars are set (`SECRET_KEY`, `DATABASE_URL`, etc.).
6. Check **Runtime Logs** for Django/Daphne startup exceptions after redeploy.

### `Invalid HTTP_HOST header: '10.x.x.x:8080'`, `'100.x.x.x:8080'`, or `'*.ondigitalocean.app'`

Cause: App Platform readiness probes call `/health/` with an internal IP as `Host` (`10.x` or `100.64/10`). Middleware rewrites that Host using `APP_DOMAIN` / `ALLOWED_HOSTS`. If those vars contain a literal wildcard like `*.ondigitalocean.app`, Django rejects it (RFC 1034) — wildcards are not valid Host header values.

Fix: redeploy the latest middleware, and set a **concrete** hostname:

```text
APP_DOMAIN=your-app-xxxxxx.ondigitalocean.app
ALLOWED_HOSTS=your-app-xxxxxx.ondigitalocean.app,.ondigitalocean.app
```

Use `.ondigitalocean.app` (leading dot) to allow all DO subdomains — not `*.ondigitalocean.app`.

### Google `Error 400: redirect_uri_mismatch`

Open the error details. If you see:

```text
redirect_uri=http://seal-app-22qre.ondigitalocean.app/accounts/google/login/callback/
```

(note **http**, not https) the app built the wrong scheme behind App Platform’s TLS proxy.

Fix in code: production sets `ACCOUNT_DEFAULT_HTTP_PROTOCOL=https` and `USE_X_FORWARDED_HOST=True`. Redeploy that commit.

In Google Cloud Console, register the **https** URI only:

```text
https://seal-app-22qre.ondigitalocean.app/accounts/google/login/callback/
```

Authorized JavaScript origin:

```text
https://seal-app-22qre.ondigitalocean.app
```
