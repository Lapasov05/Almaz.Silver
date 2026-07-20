# TZ 3-bo'lim: Python 3.12+. Bitta image api va worker (Celery) uchun ishlatiladi.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# argon2/cffi va asyncpg build uchun minimal tizim paketlari
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Standart buyruq — docker-compose'da har servis o'z command'ini beradi
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
