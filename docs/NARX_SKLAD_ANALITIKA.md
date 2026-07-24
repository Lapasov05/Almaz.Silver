# Narx (kurssiz) + Sklad nazorati + Sotuv analitikasi (migratsiya `0011`)

> Talab: og'irlik/kurs kalkulyatorini butunlay olib tashlash · narx faqat asl + chegirma ·
> sklad nazorati (status + kam qolganlar) · sotuv/so'ralgan analitikasi. **Aniq ishlashi shart.**
> **Holat: bajarildi va tekshirildi — 14/14 test.**

---

## 1. Kurs / og'irlik kalkulyatori — BUTUNLAY OLIB TASHLANDI

O'chirildi: `kurs` jadvali, `/catalog/kurs*`, `/catalog/price-calc`, `product.weight_grams`,
`category.active_gram_price`. Endi hech qanday gramm-hisob yo'q — narx aniq kiritiladi.

## 2. Narx: asl + chegirma

| Maydon | Ma'nosi |
|---|---|
| **`price`** | Asl (eski) narx — **majburiy**. Masalan `400000`. Chizib ko'rsatiladi. |
| **`discount_price`** | Chegirma (yangi) narx — ixtiyoriy. Masalan `299000`. Mijoz **shuni** to'laydi. |
| **`effective_price`** | Javobда hisoblab beriladi: **chegirma bo'lsa — o'sha, `null` bo'lsa — `price`**. |

- Mahsulot yaratishда `price` bo'lmasa → **422** (majburiy).
- `discount_price > price` bo'lsa → xato (chegirma asldan katta bo'lolmaydi).
- Buyurtma va AI **`effective_price`** ni oladi.

```jsonc
// chegirmali uzuk:
{ "name_uz": "Uzuk", "price": 400000, "discount_price": 299000 }
//  -> effective_price = 299000  (mijoz to'laydi), price=400000 chizilgan
// chegirmasiz:
{ "name_uz": "Uzuk", "price": 500000 }
//  -> effective_price = 500000
```

## 3. `engraving_available` nima? (savolingizga javob)

Bu — **uzukka ism yozish (gravyurka) xizmati** shu mahsulotга ruxsat etilganmi degani (`true/false`).
- `true` bo'lsa: AI mijozga ism yozdirishni taklif qiladi; buyurtmада `engraving_text` (ism) berilsa,
  narxга qo'shimcha `engraving_price` qo'shiladi (mahsulotда yo'q bo'lsa Settings'dagi narx).
- `false` bo'lsa: bu xizmat taklif qilinmaydi, ism qabul qilinmaydi.
- Narx tartibi: `product.engraving_price` (bo'lsa) → aks holda `settings.engraving_price` (default 50000).

## 4. Sklad nazorati

**Status** (allaqachon bor): `draft` (qoralama) · `active` (faol) · `archived` (arxiv) — `status` maydoni.

**Kam qolgan mahsulotlar** (admin qayta zakaz qilishi uchun):
- Chegara: **global sozlama** `low_stock_threshold` (default **10**) + istalgan mahsulotда
  **o'z chegarasi** (`low_stock_threshold` maydoni; bo'sh bo'lsa global ishlatiladi).
- Endpoint: **`GET /catalog/products/low-stock?status=active`** — mavjud zaxira chegaradan kam
  bo'lgan mahsulotlar (faqat `stocked` variantlar bo'yicha), pagination bilan.
- Mahsulot javobida **`available`** maydoni — umumiy mavjud zaxira (faol variantlar `stock−reserved`).

```
Global: low_stock_threshold = 10
Uzuk A (stock 3, o'z chegarasi yo'q)     -> 3 < 10  -> kam qolgan ✅
Qimmat uzuk (stock 50, o'z chegarasi 60) -> 50 < 60 -> kam qolgan ✅
Uzuk B (stock 50, chegara yo'q)          -> 50 >= 10 -> ro'yxatda yo'q
```

## 5. Sotuv analitikasi — `GET /analytics/top-products`

Eng ko'p **so'ralgan / sotilgan** mahsulotlar (order_item bo'yicha aniq hisob, taxminsiz).
`?date_from&date_to&limit` bilan.

| Maydon | Ma'nosi |
|---|---|
| `ordered_qty` | **So'ralgan** dona — barcha buyurtmalarда (talab) |
| `orders_count` | Nechta buyurtmada uchragan |
| `sold_qty` | **Sotilgan** dona — faqat to'lovi tasdiqlangan (confirmed va keyingi statuslar) |
| `revenue` | Daromad — sotilganlardan `(unit_price + engraving_price) × quantity` |

Reyting: **`sold_qty` bo'yicha kamayish** tartibida.

## Muhim: topilgan va tuzatilgan bug

Test `clear_primary()` da xatoni topdi: u eski `list_cards()` ni chaqirardi, u endi pagination
talab qiladi → **asosiy karta qo'shishда yiqilardi**. To'g'ridan-to'g'ri so'rovga o'zgartirildi.

## O'zgargan fayllar

`catalog/{models,schemas,repository,service,router}.py` · `analytics/{service,router}.py` ·
`settings/defaults.py` · `payments/repository.py` (clear_primary fix) · `demo_seed.py` ·
`migrations/versions/0011_drop_kurs_low_stock.py`

## ⚠️ Frontend uchun (o'zgarishlar)

- Mahsulot yaratishда **`price` majburiy**; `weight_grams`/kurs/`price-calc` endi **yo'q**.
- Mahsulot javobida yangi: `effective_price`, `available`, `low_stock_threshold`.
- Yangi: `GET /catalog/products/low-stock`, `GET /analytics/top-products`.

## Tekshirildi

| Test | Natija |
|---|:--:|
| Migratsiya 0001→0011 (kurs/weight olib, low_stock qo'shish) | ✅ 11/11 |
| Narx + sklad + analitika smoke (ASGI) | ✅ **14/14** |

Tasdiqlar: kurs/price-calc 404 · price majburiy (422) · effective_price (chegirmali/chegirmasiz) ·
low-stock (global 10 + mahsulot override 60) · top-products (so'ralgan/sotilgan/daromad, sold bo'yicha reyting) ·
demo_seed (7 buyurtma + karta) muvaffaqiyatli.

## Deploy
```bash
git pull
docker compose up -d --build     # 0011 migratsiya avtomatik
```
