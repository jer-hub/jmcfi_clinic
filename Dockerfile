FROM node:22-bookworm-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY frontend ./frontend
COPY core/templates ./core/templates
COPY templates ./templates
COPY appointments/templates ./appointments/templates
COPY medical_records/templates ./medical_records/templates
COPY dental_records/templates ./dental_records/templates
COPY document_request/templates ./document_request/templates
COPY feedback/templates ./feedback/templates
COPY health_tips/templates ./health_tips/templates
COPY health_forms_services/templates ./health_forms_services/templates
COPY analytics/templates ./analytics/templates
COPY pharmacy/templates ./pharmacy/templates
COPY messaging/templates ./messaging/templates
COPY staticfiles/js ./staticfiles/js

RUN mkdir -p staticfiles/css && npm run build:css


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

COPY . .
COPY --from=frontend /app/staticfiles/css/app.css ./staticfiles/css/app.css

ENV DJANGO_SETTINGS_MODULE=backend.settings \
    SECRET_KEY=build-time-only-not-for-production

RUN python manage.py collectstatic --noinput

RUN chmod +x scripts/start.sh \
    && adduser --disabled-password --gecos "" app \
    && chown -R app:app /app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["bash", "scripts/start.sh"]
