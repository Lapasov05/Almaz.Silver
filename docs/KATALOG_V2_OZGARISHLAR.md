# Katalog v2 — o'zgarishlar hisoboti (migratsiya `0009_catalog_i18n`)

> Talab: mahsulot nomi/tavsifi uz+ru · kategoriya to'liq CRUD · «kim uchun» / material / tosh —
> DB'dan (CRUD bilan, qo'lda yozilmaydi) · kategoriyaga qarab og'irlik kalkulyatori ·
> narxda current + skidka · rasmni shu API'da qo'shish (URL).
> **Holat: bajarildi va tekshirildi (17/17 + 13/13 test).**

---

## 1. Ko'p tilli (uz / ru)

| Jadval | Eski | Yangi |
|---|---|---|
| `product` | `name`, `description` | **`name_uz`**, **`name_ru`**, **`description_uz`**, **`description_ru`** |
| `category` | `name` | **`name_uz`**, **`name_ru`** |
| `gender` / `material` / `stone` | — | `name_uz`, `name_ru` |

- Mavjud ma'lumot avtomatik ko'chdi: eski `name` → `name_uz`, `description` → `description_uz`.
- **Qidiruv ikkala tilda ishlaydi:** `search_vector` (GIN) endi `name_uz + name_ru + description_uz + description_ru + ai_keywords` dan quriladi. Test: "Malika" ham, "Малика" ham topadi.

## 2. Reference lug'atlar (DB'dan, to'liq CRUD)

Uchta yangi jadval — bir xil tuzilma: `name_uz`, `name_ru`, `is_active`, `sort_order`.

| Jadval | Nima uchun | Boshlang'ich qiymatlar (seed) |
|---|---|---|
| `gender` | «Kim uchun» | Erkak / Ayol / Uniseks |
| `material` | Material | Kumush 925 + rodiy |
| `stone` | Tosh turi | Serkon |

**Endpointlar (har biri uchun bir xil CRUD):**
```
GET    /catalog/genders          GET /catalog/genders/{id}
POST   /catalog/genders          PATCH /catalog/genders/{id}     DELETE /catalog/genders/{id}
GET    /catalog/materials  ...   (xuddi shunday)
GET    /catalog/stones     ...   (xuddi shunday)
```
`?only_active=true` — faqat faollarini qaytaradi (formada ko'rsatish uchun).

**Mahsulotда:** `gender_id`, `material_id`, `stone_id` (FK). Eski matn ustunlari (`gender`, `material`, `stone`) o'chirildi, qiymatlari yangi jadvallarga ko'chirildi.

## 3. Kategoriya — to'liq CRUD + gramm narxi

```
POST /catalog/categories        GET /catalog/categories
GET  /catalog/categories/{id}   PATCH /catalog/categories/{id}   DELETE /catalog/categories/{id}
```
Maydonlar: `name_uz`, `name_ru`, `slug` (bo'sh bo'lsa nomdan), `parent_id`, **`gram_price`**.

## 4. Og'irlik kalkulyatori

- `category.gram_price` (1 gramm narxi) + `product.weight_grams`.
- **Narx berilmasa** avtomatik hisoblanadi: `price = weight_grams × gram_price`.
- **Narx qo'lda berilsa** — kalkulyator ishlamaydi, qo'lda yozilgan narx ustun.
- `weight_grams` yoki `category_id` o'zgartirilsa (`PATCH`) va narx qo'lda berilmasa — qayta hisoblanadi.
- Oldindan ko'rish endpointi (saqlamaydi):
  ```
  GET /catalog/price-calc?category_id=<id>&weight_grams=3.0
  → {"gram_price": 150000, "weight_grams": 3.0, "price": 450000}
  ```

> ⚠️ **Eslatma:** bu TZ'dagi «narx qat'iy, grammga bog'liq emas» qoidasiga zid. Siz shu variantni tanladingiz. Xavfsiz shaklda qilindi: kalkulyator narxni faqat **to'ldirib beradi**, DB'da saqlangan narx baribir yagona manba — AI va buyurtma o'sha saqlangan narxni oladi, ya'ni **guardrail buzilmaydi** (AI narx o'ylab topmaydi).

## 5. Narx: asosiy + chegirmali

| Maydon | Ma'nosi |
|---|---|
| `price` | **Asosiy narx** (chizib ko'rsatiladigan, qimmat) |
| `discount_price` | **Chegirmali narx** — mijoz SHUNI to'laydi (bo'sh bo'lsa `price` to'lanadi) |
| `effective_price` | Hisoblanadigan qiymat (API javobida bor): chegirma bo'lsa o'sha, aks holda `price` |

- Eski `compare_at_price` **o'chirildi**; ma'lumot avtomatik ko'chdi:
  eski `(price=450k, compare_at=900k)` → yangi `(price=900k, discount_price=450k)`.
- **Buyurtma** `order_item.unit_price` = `effective_price` (mijoz to'laydigan narx).
- **AI** brief'da: `price` = to'lanadigan narx, `old_price` = chizilgan narx.
- Validatsiya: `discount_price > price` bo'lsa xato qaytadi.

## 6. Rasm — o'sha mahsulot API'sida

`POST /catalog/products` ichida ikki usul:
```jsonc
"image_urls": ["https://.../uzuk.jpg"],           // eng sodda — faqat URL
"media": [{"image_url": "...", "shortcode_or_url": "https://instagram.com/p/XXX/"}]
```
Alohida ham bor: `POST /catalog/products/{id}/media`, `DELETE /catalog/media/{id}`.

---

## Mahsulot yaratish — namuna

```bash
curl -X POST http://localhost:8000/catalog/products -H "Authorization: Bearer $TOKEN" \
 -H "Content-Type: application/json" -d '{
   "name_uz": "Kumush uzuk «Malika»",
   "name_ru": "Серебряное кольцо «Малика»",
   "description_uz": "Nozik ayollar uzugi",
   "description_ru": "Изящное женское кольцо",
   "category_id": "<uzuklar-id>",
   "gender_id": "<ayol-id>", "material_id": "<kumush-id>", "stone_id": "<serkon-id>",
   "weight_grams": 3.0,                 // price berilmasa: 3.0 x gram_price
   "discount_price": 450000,            // mijoz to'laydigan narx
   "status": "active",
   "engraving_available": true,
   "image_urls": ["http://localhost:8000/static/uzuk.jpg"],
   "variants": [{"stock_qty": 10}]
 }'
```

## O'zgargan fayllar

`catalog/models.py` · `catalog/schemas.py` · `catalog/repository.py` · `catalog/service.py` ·
`catalog/router.py` · `migrations/versions/0009_catalog_i18n_refs.py` ·
`ai/tools.py` (brief yangi maydonlar) · `orders/service.py` (`effective_price`) ·
`seed.py` (reference lug'atlar) · `demo_seed.py` (yangi sxema + gram_price)

## Tekshirildi

| Test | Natija |
|---|:--:|
| Migratsiya 0001→0009 (mavjud ma'lumot ko'chishi bilan) | ✅ 9/9 |
| Katalog v2 smoke (i18n, reference CRUD, kalkulyator, narx, qidiruv, AI brief) | ✅ **17/17** |
| Ixcham regressiya (buyurtma/to'lov/zaxira/audit/KPI/guardrail/AI agent) | ✅ **13/13** |

Muhim tasdiqlar: ruscha nom bo'yicha qidiruv ishlaydi · `3.0g × 150 000 = 450 000` · buyurtma chegirmali narxni oladi (450 000) · AI brief `price=450000 / old_price=900000` · guardrail avvalgidek ishlaydi.

## Deploy

```bash
git pull
docker compose up -d --build     # alembic upgrade head avtomatik (0009 qo'llanadi)
```
Migratsiya mavjud mahsulotlarni avtomatik ko'chiradi — qo'lda ish talab qilinmaydi.
Yangi lug'at qiymatlari (`Erkak/Ayol/Uniseks`, `Kumush 925 + rodiy`, `Serkon`) migratsiya va seed orqali qo'shiladi.
