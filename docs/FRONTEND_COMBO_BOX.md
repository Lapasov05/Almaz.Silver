# Frontend — Combo (to'plam) + Box (rangli quti + rasm)

> Yangi feature'lar: **Combo** (turli kategoriyadan mahsulotlar to'plami) va **Box galereyasi** (rangli qutilar + rasm).
> Migratsiya `0017`. Jonli Postgres smoke: **22/22**. (AI/integrations/order-box_id oldingi hujjatда:
> `FRONTEND_CHANGES_2026-07-27.md`.)

## Umumiy
- **Auth:** `Authorization: Bearer <access_token>`. Ruxsat: `products:*` (view/create/update/delete).
- **Pagination:** ro'yxatlar `{items, total, limit, offset}`; so'rov `?limit=&offset=`.
- **Narx:** `Numeric(12,2)` (string/number). Pul — **UZS**. Xato: `4xx` + `{"detail": "..."}`.
- **Rasm URL:** avval `POST /files` bilan yuklab, qaytgan URL'ni ishlatasiz.

---

## 1. 📦 Box — rang + galereya (yangilandi)

Har kategoriya o'z rang qutilariga ega. Har rang: alohida narx (`0=tekin`) + count + **bir nechta rasm**.

### BoxOut (javob)
```json
{
  "id": "uuid", "category_id": "uuid",
  "name_uz": "Qizil", "name_ru": null, "color_hex": "#E53935",
  "price": "5000.00", "is_free": false,
  "stock_qty": 10, "reserved_qty": 2, "available": 8,
  "is_active": true, "sort_order": 0,
  "media": [
    { "id": "uuid", "image_url": "https://.../uploads/2026/07/red.jpg", "sort_order": 0 }
  ],
  "created_at": "2026-07-28T10:00:00Z"
}
```

### Endpointlar
| Method | Path | Body | Javob |
|---|---|---|---|
| GET | `/catalog/categories/{category_id}/boxes?only_active=&limit=&offset=` | — | `Page[BoxOut]` |
| POST | `/catalog/categories/{category_id}/boxes` | `{name_uz, color_hex?, price?, stock_qty?, is_active?, sort_order?}` | `BoxOut` |
| GET | `/catalog/boxes/{box_id}` | — | `BoxOut` |
| PATCH | `/catalog/boxes/{box_id}` | `{name_uz?, color_hex?, price?, is_active?, sort_order?}` | `BoxOut` |
| DELETE | `/catalog/boxes/{box_id}` | — | `204` (soft delete) |
| POST | `/catalog/boxes/{box_id}/stock` | `{stock_qty}` yoki `{delta}` | `BoxOut` |
| **POST** | **`/catalog/boxes/{box_id}/media`** | `{image_url, sort_order?}` | `BoxOut` (yangi rasm bilan) |
| **DELETE** | **`/catalog/boxes/media/{media_id}`** | — | `204` |

### Frontend TODO (box)
- Kategoriya sahifasi: ranglar (swatch=`color_hex`) + **rasm galereyasi** (yuklash: `/files` → `image_url` → `POST .../media`).
- `price=0` → "Tekin" belgisi. `available` — mijozga taklif qilinadigan son.

---

## 2. 🧩 Combo (to'plam) — YANGI

Combo = turli kategoriyadan bir nechta mahsulot to'plami. **O'z nomi, narxi, rasmlari** bor;
ichida qaysi mahsulotlar borligini (rasmi bilan) ko'rsatadi. Combo — maxsus mahsulot (`is_combo`),
"Combo" kategoriyada saqlanadi.

**Muhim (zaxira):** combo **o'z zaxirasiga ega emas** — sotilганда **ichidagi mahsulotlar** zaxirasi
kamayadi. Combo mavjudligi (`available`) = ichidagilarning eng kamiga qarab (`min(komponent.available ÷ soni)`).

### ComboOut (javob)
```json
{
  "id": "uuid",
  "name_uz": "Sevgi to'plami", "name_ru": null, "description_uz": null,
  "price": "450000.00", "old_price": null,
  "status": "active",
  "variant_id": "uuid",          // buyurtma uchun (order_item.variant_id shu bo'ladi)
  "available": 2,                // min(komponent.available // quantity)
  "items": [
    {
      "combo_item_id": "uuid", "variant_id": "uuid", "product_id": "uuid",
      "name_uz": "Uzuk A", "price": "200000.00", "quantity": 1,
      "available": 10, "image_url": "https://.../ring.jpg"
    },
    { "combo_item_id": "uuid", "variant_id": "uuid", "product_id": "uuid",
      "name_uz": "Braslet B", "price": "150000.00", "quantity": 2, "available": 8, "image_url": null }
  ],
  "images": ["https://.../combo1.jpg"],   // combo o'z galereyasi
  "created_at": "2026-07-28T10:00:00Z"
}
```

### Endpointlar
| Method | Path | Body | Javob |
|---|---|---|---|
| POST | `/catalog/combos` | `ComboCreate` | `ComboOut` |
| GET | `/catalog/combos?status=&q=&limit=&offset=` | — | `Page[ComboOut]` |
| GET | `/catalog/combos/{combo_id}` | — | `ComboOut` |
| PATCH | `/catalog/combos/{combo_id}` | `{name_uz?, name_ru?, description_uz?, price?, discount_price?, status?}` | `ComboOut` |
| DELETE | `/catalog/combos/{combo_id}` | — | `204` (soft delete) |
| POST | `/catalog/combos/{combo_id}/items` | `{variant_id, quantity?}` | `ComboOut` (element qo'shildi) |
| DELETE | `/catalog/combos/items/{item_id}` | — | `204` (element o'chirildi) |

**ComboCreate:**
```json
{
  "name_uz": "Sevgi to'plami",
  "name_ru": null,
  "description_uz": "Uzuk + braslet",
  "price": 450000,
  "discount_price": null,
  "status": "active",
  "items": [
    { "variant_id": "<uzuk variant id>", "quantity": 1 },
    { "variant_id": "<braslet variant id>", "quantity": 2 }
  ]
}
```
- `items[].variant_id` — komponent mahsulotning varianti (odatda default varianti; mahsulot detalidan olinadi).
- Combo ichiga **combo qo'shib bo'lmaydi** (`400`).

**Combo rasmlari (galereya):** combo — mahsulot, shuning uchun **mavjud mahsulot media endpointi** ishlatiladi:
`POST /catalog/products/{combo_id}/media {image_url}`. Natija `ComboOut.images` da chiqadi.

### Combo'ni buyurtma qilish
Combo'ni buyurtmaga qo'shish — oddiy mahsulotdek, faqat `variant_id` = **combo'ning `variant_id`**si:
```json
POST /orders
{ "customer_id": "uuid", "items": [ { "variant_id": "<ComboOut.variant_id>", "quantity": 1 } ] }
```
- Narx = combo `price`. Ichidagi komponentlar zaxirasi avtomatik band bo'ladi.
- Zaxira yetmasa `400` ("Zaxira yetarli emas (SKU ...)").

### Frontend TODO (combo)
- **Combo yaratish sahifasi:** nom, narx, tavsif + mahsulot qidirib **variant tanlash** (turli kategoriyadan) + soni; combo rasmlari yuklash.
- **Combo ko'rsatish:** `items[]` (har biri rasm + nom + soni), `available`, `price`; mavjud bo'lmasa (`available=0`) "tugagan".
- **Checkout:** combo'ni `variant_id` bilan buyurtmaga qo'shish.

---

## Demo ma'lumot (test uchun)
```bash
make demo-seed      # kategoriyalar + mahsulotlar
make demo-boxes     # har kategoriyaga 6 rang (2 tekin + 4 pulli) + rasm
make demo-combos    # mavjud mahsulotlardan combolar
```

## Tekshirildi: 22/22 (jonli Postgres)
Combo: yaratish · zaxira komponentlarda (order/approve/reject/cancel) · available=min · combo-ichida-combo→xato ·
AI combo detali. Box: media add/delete · non-combo order+to'lov (regressiya). Demo: idempotent.
