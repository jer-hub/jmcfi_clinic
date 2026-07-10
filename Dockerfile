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

RUN python manage.py collectstatic --noinput

RUN adduser --disabled-password --gecos "" app && chown -R app:app /app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["daphne", "-b", "0.0.0.0", "-p", "8080", "backend.asgi:application"]
