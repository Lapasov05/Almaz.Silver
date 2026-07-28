# Frontend — Mahsulot yaratish: RASM MAJBURIY

> Yangi qoida: `POST /catalog/products` endi **kamida bitta rasm** talab qiladi.
> Sabab: mijoz mahsulotni nom bilan tanimasligi mumkin — AI tavsiya qilganda **rasmini yuboradi**
> (`send_product_images`). Rasmsiz mahsulot yaratib bo'lmaydi.

## Oqim: rasm yuklab, mahsulot yaratish

### 1) Rasmni yuklash → URL
`POST /files` (multipart, `file`) — ruxsat: mavjud auth.
```json
// javob (UploadOut)
{ "url": "https://<domen>/uploads/2026/07/abc.jpg", "filename": "2026/07/abc.jpg",
  "content_type": "image/jpeg", "size": 123456 }
```
- Bir nechta rasm: `POST /files/batch` → `UploadOut[]`.

### 2) Mahsulot yaratish (rasm URL bilan)
`POST /catalog/products` (ruxsat: `products:create`) — `image_urls` ga yuqoridagi URL(lar):
```json
{
  "name_uz": "Kumush uzuk",
  "category_id": "uuid",
  "price": 200000,
  "discount_price": 180000,
  "status": "active",
  "image_urls": ["https://<domen>/uploads/2026/07/abc.jpg"],   // ← MAJBURIY (kamida 1)
  "variants": [ { "stock_qty": 10 } ]
}
```

**Rasm bermasangiz** → `400`:
```json
{ "detail": "Mahsulot uchun kamida bitta rasm majburiy (image_urls yoki media rasm URL)" }
```

## Muhim
- **Kamida 1 rasm** shart. Ko'p rasm: `image_urls` massivига bir nechta URL yoki `media: [{image_url}]`.
- Rasm URL'i **to'g'ridan-to'g'ri rasm** bo'lsin (`/files`dan). Instagram post/story LINKI rasm o'rnini
  bosmaydi (u alohida — `docs/FRONTEND_INSTAGRAM.md`).
- Bu qoida faqat oddiy mahsulotga. **Combo** (`POST /catalog/combos`) alohida — rasmini keyin
  `POST /catalog/products/{combo_id}/media` bilan qo'shasiz.

## Frontend TODO
- Mahsulot qo'shish formasida **rasm yuklash maydonini majburiy** qiling (kamida 1): fayl tanlanadi →
  `POST /files` → qaytgan `url` → `image_urls` ga. Yuborishdан oldin tekshiring (bo'sh bo'lsa bloklang).
- Bir nechta rasm — `/files/batch` yoki ketma-ket yuklab, `image_urls` massivini to'ldiring.
