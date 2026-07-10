# DigitalOcean App Platform Deployment

This runbook deploys JMCFI Clinic to DigitalOcean App Platform while keeping Supabase for database and file storage.

## 1) Prerequisites

- Supabase project with Postgres + Storage configured
- Google OAuth credentials configured for production callback
- GitHub repository connected to DigitalOcean App Platform

## 2) Create App Platform resources

1. Create a new App in DigitalOcean App Platform from this repository.
2. Choose **Dockerfile** as the build strategy.
3. Add one **Web Service** component.
4. Add one **Managed Redis** component and copy its connection string.

## 3) Web service configuration

- **HTTP Port**: `8080`
- **Health Check Path**: `/health/`
- **Build Command**: (leave empty, handled by `Dockerfile`)
- **Run Command**: (leave empty, handled by `Dockerfile`)
- **Instance count**: start with 1, scale as needed

## 4) Environment variables

Set these in the App Platform web service:

- `DEBUG=False`
- `SECRET_KEY=<strong-random-secret>`
- `ALLOWED_HOSTS=<your-app>.ondigitalocean.app,<custom-domain-if-any>`
- `CSRF_TRUSTED_ORIGINS=https://<your-app>.ondigitalocean.app,https://<custom-domain-if-any>`
- `APP_DOMAIN=<your-app>.ondigitalocean.app`
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
