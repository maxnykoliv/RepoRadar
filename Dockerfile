FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser \
    && mkdir /data && chown appuser /data

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=appuser:appuser . .
# collectstatic only needs a key to import settings; the real one comes from the environment at runtime.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

USER appuser
ENV SQLITE_PATH=/data/db.sqlite3
VOLUME /data
EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
