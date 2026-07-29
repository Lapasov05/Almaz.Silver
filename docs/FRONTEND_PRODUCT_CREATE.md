# Frontend — Mahsulot qo'shish (`POST /catalog/products`) yo'llanmasi

> Bu hujjat **frontend dasturchisi** uchun — katalogga mahsulot qo'shish API'sini to'liq qamrab
> oladi: autentifikatsiya, ma'lumotnoma (kategoriya/gender/material/tosh), rasm yuklash, mahsulot
> yaratish (**stock bilan**), javob, va bog'liq endpointlar (variant/stock/media).

**Backend bazaviy URL (prod):** `https://almaz.api.cognilabs.org`
**Barcha so'rovlar:** `Authorization: Bearer <access_token>` + `Content-Type: application/json`
(rasm yuklashdan tashqari — u `multipart/form-data`).

---

## 0. MUHIM tushunchalar (chalkashmaslik uchun)

| Qoida | Izoh |
|---|---|
| **Zaxira (stock) — variant ichida** | Mahsulotда emas, `variants[].stock_qty` da. Bitta oddiy mahsulot = 1 variant. |
| **O'lcham — variant EMAS** | Uzuk o'lchami buyurtmada belgilanadi. Har xil o'lcham uchun alohida variant YARATMANG. Variant faqat SKU/zaxira uchun. |
| **`requires_ring_size` — kategoriyadan** | Uzuk kategoriyasida `requires_ring_size=true` bo'lsa, buyurtmada o'lcham so'raladi. Mahsulotда emas, KATEGORIYAда. |
| **Rasm MAJBURIY** | Har mahsulotда kamida 1 rasm (`image_urls` yoki `media`). Rasmsiz `400`. |
| **Narx** | `price` = asl (chizilgan) narx. `discount_price` (ixtiyoriy) = chegirma. Mijoz `discount_price` bo'lsa o'shani, aks holda `price` to'laydi. `discount_price ≤ price`. |

---

## 1. Autentifikatsiya

```http
POST /auth/login
Content-Type: application/json

{ "email": "admin@almazsilver.uz", "password": "••••••" }
```
Javob: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`
→ keyingi so'rovlarда `Authorization: Bearer <access_token>`.

Mahsulot qo'shish uchun `products:create` ruxsati kerak (admin/menejer rollarida bor).

---

## 2. Ma'lumotnoma ID'lari (ixtiyoriy, lekin tavsiya)

`category_id`, `gender_id`, `material_id`, `stone_id` — hammasi **ixtiyoriy** (yubormasangiz `null`).
Ular UUID; ID'larni quyidagilardan olasiz:

| Ma'lumot | Endpoint |
|---|---|
| Kategoriyalar | `GET /catalog/categories` |
| Gender (Erkak/Ayol/Uniseks) | `GET /catalog/genders` |
| Material (Kumush 925 + rodiy) | `GET /catalog/materials` |
| Tosh (Serkon) | `GET /catalog/stones` |

Har biri `{ items: [ { id, name_uz, name_ru, ... } ], total }` qaytaradi. Formada **select/dropdown**
qilib ID'ni tanlatasiz.

> **Kategoriya muhim:** uzuk kategoriyasida `requires_ring_size=true` bo'lsin (buyurtmada o'lcham
> so'ralishi uchun). Kategoriya yaratish: `POST /catalog/categories`
> `{ "name_uz": "Uzuklar", "slug": "uzuklar", "requires_ring_size": true }`.

---

## 3. Rasm yuklash (mahsulotdan OLDIN)

Mahsulot rasmini avval yuklab, qaytgan **URL**ni mahsulotга berasiz.

```http
POST /files
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <rasm fayli>            # jpg, jpeg, png, webp, gif, heic, pdf
```
Javob:
```json
{ "url": "https://almaz.api.cognilabs.org/uploads/2026/07/ab12...jpg",
  "filename": "2026/07/ab12...jpg", "content_type": "image/jpeg", "size": 84213 }
```
Bir nechta rasm: `POST /files/batch` (`files: [ ... ]`) → `[{url}, ...]`.

> Qaytgan `url` — **public** URL. Shu URL mahsulotга `image_urls`ga beriladi va AI mijozga shu rasmni
> yuboradi. (Serverда `PUBLIC_BASE_URL` haqiqiy https domen bo'lishi kerak — bu backend sozlamasi.)

---

## 4. Mahsulot yaratish — `POST /catalog/products`

### 4.1. ENG SODDA (stock bilan) — tavsiya etilgan minimal

```http
POST /catalog/products
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{
  "name_uz": "Nozik ayollar uzugi 'Malika'",
  "price": 900000,
  "status": "active",
  "image_urls": ["https://almaz.api.cognilabs.org/uploads/2026/07/ab12...jpg"],
  "variants": [
    { "stock_qty": 50 }
  ]
}
```
> **STOCK shu yerда:** `variants[].stock_qty`. Yubormasangiz **default `0`** (1 emas!) — shuning
> uchun har doim `variants: [{ "stock_qty": N }]` yuboring. SKU bermasangiz avtomatik yaraladi.

### 4.2. TO'LIQ (barcha maydonlar)

```json
{
  "name_uz": "Nozik ayollar uzugi 'Malika'",
  "name_ru": "Изящное женское кольцо 'Malika'",
  "description_uz": "Kunlik kiyishga mos, yengil dizayn.",
  "description_ru": "...",
  "category_id": "7c1e...uuid",
  "gender_id": "a9f0...uuid",
  "material_id": "b3d2...uuid",
  "stone_id": "c5e1...uuid",
  "price": 900000,
  "discount_price": 780000,
  "status": "active",
  "ai_keywords": ["ayollar uzuk", "nozik", "kundalik"],
  "engraving_available": true,
  "engraving_price": 50000,
  "low_stock_threshold": 5,
  "image_urls": [
    "https://almaz.api.cognilabs.org/uploads/2026/07/img1.jpg",
    "https://almaz.api.cognilabs.org/uploads/2026/07/img2.jpg"
  ],
  "variants": [
    { "sku": "MALIKA-001", "stock_qty": 50, "fulfillment_type": "stocked" }
  ]
}
```

### 4.3. Maydonlar jadvali

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| `name_uz` | string | **HA** | Mahsulot nomi (o'zbekcha) |
| `name_ru` | string | yo'q | Ruscha nom |
| `description_uz` / `description_ru` | string | yo'q | Tavsif |
| `category_id` | uuid | yo'q | `GET /catalog/categories` dan |
| `gender_id` | uuid | yo'q | `GET /catalog/genders` dan |
| `material_id` | uuid | yo'q | odatда "Kumush 925 + rodiy" |
| `stone_id` | uuid | yo'q | odatда "Serkon" |
| `price` | number ≥0 | **HA** | Asl (chizilgan) narx |
| `discount_price` | number ≥0 | yo'q | Chegirma narx (`≤ price` bo'lishi shart) |
| `status` | enum | yo'q (default `draft`) | `draft` \| `active` \| `archived`. **Sotuvда ko'rinishi uchun `active`** |
| `ai_keywords` | string[] | yo'q | Qidiruv kalit so'zlari (AI topishi uchun) |
| `engraving_available` | bool | yo'q (default `false`) | Gravyurka (ism yozish) mumkinmi |
| `engraving_price` | number | yo'q | Gravyurka narxi (bo'sh → Settings'dagi standart) |
| `low_stock_threshold` | int | yo'q | "Kam qoldi" chegarasi (bo'sh → global) |
| `image_urls` | string[] | **HA*** | `/files` dan qaytgan URL(lar). Kamida bitta rasm shart |
| `media` | object[] | HA* | Muqobil: `[{ "image_url": "..." }]` (image_urls o'rniga) |
| `variants` | object[] | yo'q | **Stock shu yerда**. Berilmasa 0 stock'li default variant yaraladi |

*Rasm: `image_urls` **yoki** `media[].image_url` — kamida bittasi majburiy.

### 4.4. `variants[]` (VariantCreate)

| Maydon | Tur | Default | Izoh |
|---|---|---|---|
| `stock_qty` | int ≥0 | **0** | Zaxira soni — buni bering! |
| `sku` | string | avto-generatsiya | Ombor kodi (unikal) |
| `barcode` | string | null | Shtrix-kod |
| `fulfillment_type` | enum | `stocked` | `stocked` (zaxiradan) \| `made_to_order` (buyurtmaga) \| `unique` (yakka) |
| `is_active` | bool | `true` | |

> **1 tadan ortiq variant kerak emas** oddiy mahsulotга. O'lcham uchun variant ochManG (o'lcham
> buyurtmada). Bir nechta variant faqat haqiqiy SKU farqi bo'lganда.

---

## 5. Javob (`200`) — `ProductOut`

```json
{
  "id": "d4e5...uuid",
  "name_uz": "Nozik ayollar uzugi 'Malika'",
  "price": 900000.00,
  "discount_price": 780000.00,
  "effective_price": 780000.00,      // mijoz to'laydigan narx
  "status": "active",
  "available": 50,                   // umumiy mavjud zaxira (barcha variantlar)
  "requires_ring_size": true,        // kategoriyadan
  "engraving_available": true,
  "engraving_price": 50000.00,
  "gender": { "id": "...", "name_uz": "Ayol" },
  "material": { "id": "...", "name_uz": "Kumush 925 + rodiy" },
  "stone": { "id": "...", "name_uz": "Serkon" },
  "variants": [
    { "id": "v1...uuid", "sku": "MALIKA-001", "stock_qty": 50, "reserved_qty": 0, "available": 50 }
  ],
  "media": [ { "id": "...", "image_url": "https://.../img1.jpg" } ]
}
```
- `available` = `stock_qty − reserved_qty` (barcha variantlar yig'indisi).
- `variants[].id` — keyin stockni o'zgartirish uchun kerak (6-bo'lim).

---

## 6. Stockni keyin o'zgartirish / variant qo'shish

### 6.1. Mavjud variant stockini o'zgartirish
```http
POST /catalog/variants/{variant_id}/stock
```
```json
{ "stock_qty": 100 }     // aniq qiymatga o'rnatadi
```
yoki
```json
{ "delta": 20 }          // qo'shadi (manfiy = kamaytiradi, masalan -5)
```
`variant_id` — `ProductOut.variants[].id` dan.

### 6.2. Mavjud mahsulotga yangi variant qo'shish
```http
POST /catalog/products/{product_id}/variants
{ "sku": "MALIKA-002", "stock_qty": 30 }
```

### 6.3. Mahsulotni yangilash (narx/status/tavsif)
```http
PATCH /catalog/products/{product_id}
{ "status": "active", "discount_price": 700000 }
```
> Stock bu yerда EMAS — stock faqat variant endpointlari orqali (6.1).

### 6.4. Yana rasm qo'shish
```http
POST /catalog/products/{product_id}/media
{ "image_url": "https://.../img3.jpg" }
```

---

## 7. Xatolar va validatsiya

| Holat | HTTP | `detail` |
|---|---|---|
| Rasmsiz | `400` | "Mahsulot uchun kamida bitta rasm majburiy (image_urls yoki media rasm URL)" |
| Chegirma > asl narx | `400` | "Chegirma narx asl narxdan katta bo'lmasligi kerak" |
| Ruxsat yo'q | `403` | "..." (products:create kerak) |
| Token yo'q/eskirgan | `401` | "..." |
| Noto'g'ri maydon (validatsiya) | `422` | FastAPI validatsiya xatosi (maydon nomi bilan) |

Barcha xatolar `{ "detail": "..." }` ko'rinishida (`422` bo'lsa `detail` — massiv).

---

## 8. Frontend oqimi (yig'ma)

```
1) POST /auth/login                          → token
2) GET  /catalog/categories | genders | materials | stones   → dropdownlar (ID'lar)
3) POST /files (multipart, rasm)             → image url(lar)
4) POST /catalog/products                    → mahsulot (variants:[{stock_qty:N}] bilan!)
   (kerak bo'lsa) POST /catalog/variants/{id}/stock  → stockni sozlash
```

### Checklist
- [ ] Login → token, har so'rovда `Authorization: Bearer`.
- [ ] Kategoriya/gender/material/tosh dropdownlari (`GET` reference).
- [ ] Rasm yuklash formasi → `POST /files` → `url`.
- [ ] Mahsulot formasi: `name_uz`, `price`, `status=active`, `image_urls`, **`variants:[{stock_qty}]`**.
- [ ] (ixtiyoriy) `discount_price`, `engraving_available/price`, `ai_keywords`, description.
- [ ] Javobdagi `variants[].id` ni saqlang (stockni keyin boshqarish uchun).
- [ ] Xatolar: 400 (rasm/chegirma), 422 (validatsiya), 401/403 (auth).

> **Eng ko'p uchraydigan xato:** `variants` yubormaslik → mahsulot **0 stock** bilan chiqadi.
> Har doim `variants: [{ "stock_qty": <son> }]` yuboring.
