#!/usr/bin/env bash
# PostgreSQL + MinIO backup (TZ 16). Cron orqali muntazam ishga tushiriladi.
# Namuna cron (har kuni 03:00):  0 3 * * *  /app/scripts/backup.sh >> /var/log/almaz-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# --- PostgreSQL ---
: "${POSTGRES_HOST:=postgres}" "${POSTGRES_USER:=almaz}" "${POSTGRES_DB:=almaz}"
echo "[backup] pg_dump ${POSTGRES_DB} ..."
PGPASSWORD="${POSTGRES_PASSWORD:-almaz}" pg_dump \
  -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  -f "${BACKUP_DIR}/db_${STAMP}.dump"

# --- MinIO (object storage) — mc kerak ---
if command -v mc >/dev/null 2>&1; then
  echo "[backup] minio mirror ..."
  mc alias set almaz "${S3_ENDPOINT_URL:-http://minio:9000}" \
    "${S3_ACCESS_KEY:-minioadmin}" "${S3_SECRET_KEY:-minioadmin}" >/dev/null
  mc mirror --overwrite "almaz/${S3_BUCKET:-almaz}" "${BACKUP_DIR}/objects_${STAMP}"
else
  echo "[backup] mc topilmadi — object storage backup o'tkazib yuborildi"
fi

# --- Eski backuplarni tozalash (7 kundan eski) ---
find "$BACKUP_DIR" -maxdepth 1 -name 'db_*.dump' -mtime +7 -delete || true
echo "[backup] tayyor: ${BACKUP_DIR} (${STAMP})"
