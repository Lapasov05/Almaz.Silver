# File upload API

Fayl yuklaydi va ochib ko'rsa bo'ladigan **to'liq URL** qaytaradi. Rasm yuklab, URL'ini
mahsulotning `image_urls` iga qo'yish uchun ideal.

## Endpointlar

```
POST /files          (multipart: file)   -> {url, filename, content_type, size}
POST /files/batch    (multipart: files[]) -> [{...}, {...}]
```

- **Autentifikatsiya kerak** (`Authorization: Bearer <token>`).
- Ruxsat etilgan turlar: `jpg, jpeg, png, webp, gif, pdf, heic`.
- Maksimal hajm: `UPLOAD_MAX_MB` (default 10 MB).
- Fayl nomi UUID bilan yaratiladi (`uploads/YYYY/MM/<uuid>.<ext>`) — nom to'qnashuvi/path traversal yo'q.

## Namuna

```bash
# yuklash
curl -X POST http://localhost:8000/files -H "Authorization: Bearer $TOKEN" \
  -F "file=@uzuk.jpg"
# javob:
# { "url": "http://localhost:8000/uploads/2026/07/ab12...ef.jpg",
#   "filename": "2026/07/ab12...ef.jpg", "content_type": "image/jpeg", "size": 84213 }

# qaytgan URL bevosita ochiladi (brauzer/ img src)
curl -s http://localhost:8000/uploads/2026/07/ab12...ef.jpg -o test.jpg

# keyin mahsulotga:
curl -X POST http://localhost:8000/catalog/products -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name_uz":"Uzuk","price":450000,"status":"active",
       "image_urls":["http://localhost:8000/uploads/2026/07/ab12...ef.jpg"]}'
```

## Qanday ishlaydi

- Fayllar `UPLOAD_DIR` (Docker volume `uploads_data`) ga saqlanadi — konteyner qayta qurilsa **yo'qolmaydi**.
- API ularni `/uploads/<yo'l>` orqali beradi (StaticFiles). Nginx hamma so'rovni API'ga uzatgani uchun
  tashqi domendan ham ochiladi: `https://almaz.api.cognilabs.org/uploads/...`.
- URL `PUBLIC_BASE_URL` dan quriladi — frontend to'g'ridan-to'g'ri `<img src>` da ishlatadi.

## ⚠️ Prod

`.env` da to'g'ri domen bo'lsin, aks holda URL brauzerда ochilmaydi:
```
PUBLIC_BASE_URL=https://almaz.api.cognilabs.org
UPLOAD_DIR=/code/uploads
UPLOAD_MAX_MB=10
```
Backup: `uploads_data` volume ham zaxiralanishi kerak (`scripts/backup.sh` ga qo'shsa bo'ladi).

> Eslatma: MinIO chek rasmlari uchun ishlatiladi (`/payments/receipts`). Umumiy fayl yuklash bu
> yerда ataylab lokal volume + API static orqali — chunki MinIO brauzerga ochiq emas (ichki tarmoq).

## Tekshirildi: 7/7
tokensiz→401 · yuklash→URL · URL orqali ochiladi (baytlar mos) · `.exe` rad · bo'sh fayl rad · batch · URL public base bilan.

O'zgargan: `core/config.py`, `modules/files/router.py` (yangi), `main.py` (/uploads mount + router),
`docker-compose.yml` (uploads_data volume), `.env.example`.
