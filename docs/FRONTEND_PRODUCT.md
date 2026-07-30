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
  "engraving_available": true,      // uzukka ism yozish (gravyurka) shu mahsulotda mumkinmi
  "engraving_price": 50000,         // bo'sh -> global settings.engraving_price
  "warranty_months": 24,            // KAFOLAT override; bo'sh -> global settings.warranty_months
  "resize_available": true,         // O'LCHAM o'zgartirish (zargar) — uzuk uchun; false -> taklif qilinmaydi
  "resize_price": 50000,            // bo'sh -> global settings.resize_price
  "variants": [ { "stock_qty": 10 } ]
}
```

### Qo'shimcha xizmat maydonlari (ixtiyoriy, bo'sh -> global sozlama)
| Maydon | Vazifa | Bo'sh bo'lsa |
|---|---|---|
| `warranty_months` | Kafolat muddati (oy) — shu mahsulotga | Global `settings.warranty_months` (default 12) |
| `resize_available` | Uzuk o'lchamini zargar o'zgartira oladimi (uzuklarga) | `true` (uzuk bo'lsa taklif qilinadi) |
| `resize_price` | O'lcham o'zgartirish (zargar) narxi | Global `settings.resize_price` (default 50 000) |
| `engraving_available` / `engraving_price` | Ism yozish (gravyurka) | Global `settings.engraving_*` |

> **Global sozlamalar** (`PUT /settings/{key}`): `warranty_enabled`, `warranty_months`, `warranty_text`,
> `resize_enabled`, `resize_price`, `resize_text`. Mahsulotda maydon berilsa — o'sha ustun keladi (override).
> Kafolat/o'lcham o'zgartirishni AI sotuvda **o'zi** mijozga aytadi (uzuk o'lchami noaniq bo'lsa: o'rta razmer → keyin zargar moslaydi).

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
