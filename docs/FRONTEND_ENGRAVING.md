# Frontend — Gravyurka (ism yozish) + belgi limiti

> Migratsiya `0022`. Mahsulotga ism/yozuv (gravyurka) qo'shish xizmati **har uzukka mos belgi limiti** bilan.
> Ba'zi uzuklarga atigi **3 ta belgi** (masalan `A&B`) sig'adi, ba'zilariga **to'liq ism** (`Abdug'ani & Falonchioy`).

## Qayerda? — Mahsulot qo'shish/tahrirlash formasida

`POST /catalog/products` va `PATCH /catalog/products/{id}` — gravyurka maydonlari (hammasi ixtiyoriy):

| Maydon | Tur | Vazifa | Bo'sh bo'lsa |
|---|---|---|---|
| `engraving_available` | bool | Shu uzukka ism yozish mumkinmi | `false` (taklif qilinmaydi) |
| `engraving_price` | number | Gravyurka narxi (so'm) | Global `settings.engraving_price` (50 000) |
| **`engraving_max_chars`** | int ≥1 | **Shu uzukka sig'adigan MAKS belgi soni** | Global `settings.engraving_max_chars` (20) |

**Namuna — kichik uzuk (faqat 3 belgi):**
```json
POST /catalog/products
{
  "name_uz": "Minimalist uzuk",
  "category_id": "uuid",
  "price": 300000,
  "image_urls": ["https://<domen>/uploads/.../a.jpg"],
  "engraving_available": true,
  "engraving_max_chars": 3,          // ← "A&B" sig'adi, "Abdugani" sig'maydi
  "variants": [ { "stock_qty": 10 } ]
}
```

**Namuna — katta uzuk (to'liq ism):** `engraving_max_chars` ni bermang (yoki `22`) → global 20 yoki bergan qiymat ishlaydi.

## Belgi qanday sanaladi
- **Hamma belgi** sanaladi: harflar, raqamlar, `&`, bo'sh joy (space) ham. `len(text)` bilan.
  - `"A&B"` = **3**, `"Sardor"` = **6**, `"Abdug'ani & Falonchioy"` = **22**.
- `0` = **cheksiz** (limit yo'q). Global default `20`.

## Validatsiya (backend)
Buyurtma yaratishda (`create_order`) yozuv limitdan uzun bo'lsa → `AppError`:
```json
{ "detail": "Bu uzukka eng ko'pi 3 ta belgi sig'adi, siz 8 ta yubordingiz. Iltimos, qisqaroq yozuv tanlang." }
```
Frontendда ham buyurtma/checkout formasida `engraving_text` maydoniga `maxlength = ProductOut.engraving_max_chars`
qo'ying (yoki `settings.engraving_max_chars` fallback) — mijoz ortiqcha yozib qo'ymasin.

## AI xulqi (avtomatik)
- AI `get_product_details`/`search`/`recommend` natijasida `engraving.max_chars` ni oladi.
- Mijoz limitdan **uzun** yozuv aytsa, AI buyurtma yaratmaydi, muloyim aytadi:
  *"Bu uzukka N ta belgi sig'adi, iltimos qisqaroq yozuv (masalan 'A&B') tanlang."*
- Sig'sa — buyurtmaga qo'shadi (`engraving_text`).

## Global sozlama
`PUT /settings/engraving_max_chars` `{ "value": 20 }` — global default (mahsulotда o'z qiymati bo'lsa u ustun keladi).
Yana: `engraving_enabled` (butun xizmatni yoqish/o'chirish), `engraving_price`.

## ProductOut javobida
`GET /catalog/products/{id}` endi `engraving_max_chars` (int yoki `null`) qaytaradi — formada shu qiymatni ko'rsating.
