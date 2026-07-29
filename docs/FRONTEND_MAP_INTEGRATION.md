# Frontend — Lokatsiya (xarita) sahifasi integratsiyasi

> Bu hujjat **frontend dasturchisi** uchun. Almaz AI sotuvchi mijozga buyurtma manzilini
> olish uchun bir martalik **xarita linki** yuboradi. Frontend shu sahifani ko'rsatadi,
> mijozdan lokatsiya oladi. Backend zonani (Toshkent/BTS) aniqlaydi; BTS bo'lsa mijozga
> **yaqin filiallar ro'yxatini** qaytaradi va mijoz **birini tanlaydi**.

**Backend bazaviy URL (prod):** `https://almaz.api.cognilabs.org`
**Frontend map sahifasi:** `https://almaz-steel.vercel.app/map/{token}`

---

## 1. Umumiy oqim (IKKI QADAMLI)

```
AI (Instagram/Telegram) → mijozga link:  https://almaz-steel.vercel.app/map/{token}
        │
        ▼
Frontend  /map/{token}  sahifasi ochiladi → xarita
        │
        │  ── 1-QADAM: RESOLVE (token YOPILMAYDI) ─────────────────
        │  Mijoz xaritada joy belgilaydi (lat/lng)
        │  POST {API}/map/{token}/resolve   { lat, lng }
        │      → location_type = "Toshkent"  → filiallar yo'q, narx 50 000
        │      → location_type = "BTS"       → yaqin FILIALLAR ro'yxati, narx 30 000
        │
        │  ── (faqat BTS) Mijoz ro'yxatdan filialni tanlaydi ──────
        │
        │  ── 2-QADAM: CONFIRM (token YOPILADI) ───────────────────
        │  POST {API}/map/{token}/confirm   { lat, lng, bts_branch_id? }
        │      → mijoz lokatsiyasi + tanlangan filial saqlanadi, narx buyurtmaга qo'shiladi
        ▼
Frontend: "Rahmat! Chatga qayting" — AI to'lov karta raqamini yuboradi (bu sahifada EMAS)
```

- **Toshkent** (shahar ichi): filial tanlash YO'Q. Resolve `branches: []` qaytaradi → to'g'ridan
  confirm (bts_branch_id kerak emas). Narx **50 000**. Kuryer manzilga yetkazadi.
- **BTS** (Toshkentdan tashqarida): resolve mijozning **viloyat/tumanidagi filiallarni** (masofa
  bo'yicha) qaytaradi. Mijoz birini tanlaydi → confirm `bts_branch_id` bilan. Narx **30 000**.
  Mijoz shu filialdan oladi.
- `{token}` — bir martalik. **Faqat `confirm` muvaffaqiyatli bo'lganda yopiladi** (`resolve`
  ni istagancha qayta chaqirsa bo'ladi). Har buyurtma uchun AI yangi link yuboradi. Mijozda
  bir vaqtda **bitta faol buyurtma** bo'ladi — chalkashlik yo'q.

---

## 2. API kontrakti

### 2.1. `GET /map/{token}` — sahifa konteksti (ixtiyoriy)

Sahifa ochilganda buyurtma raqami/summasini ko'rsatish uchun.

**Response `200`:**
```json
{ "order_no": "ORD-260729-EE7220", "items_total": 780000.0,
  "zones": { "tashkent": 50000.0, "region": 30000.0 } }
```

---

### 2.2. `POST /map/{token}/resolve` — 1-qadam (zona + filiallar) — **token yopilmaydi**

Mijoz xaritada joy belgilagach chaqiring.

**Request body:**
```json
{ "lat": 39.654, "lng": 66.959 }
```
| Maydon | Majburiy | Izoh |
|---|---|---|
| `lat` / `lng` | **HA** | Mijoz belgilagan nuqta. Zona SHU asosda aniqlanadi. |

**Response `200` — BTS (Toshkentdan tashqarida):**
```json
{
  "order_no": "ORD-260729-EE7220",
  "location_type": "BTS",
  "delivery_fee": 30000.0,
  "items_total": 780000.0,
  "grand_total": 810000.0,
  "requires_branch_selection": true,
  "branches": [
    {
      "id": "0f3c...uuid", "name": "SAMARKAND SIYOB",
      "region": "Samarqand", "district": "Samarqand shahar",
      "address": "Samarqand sh, ... 5-uy", "landmark": "... yonida",
      "phone": "1230", "work_hours": "Du-Shan: 09:00-18:00; Yak: Dam olish",
      "lat": 39.6542, "lng": 66.9597, "distance_km": 1.2
    }
    /* ... masofa bo'yicha yaqindan uzoqqa (eng ko'pi 30 ta) ... */
  ]
}
```

**Response `200` — Toshkent (shahar ichi):**
```json
{
  "order_no": "ORD-260729-EE7220",
  "location_type": "Toshkent",
  "delivery_fee": 50000.0,
  "items_total": 780000.0,
  "grand_total": 830000.0,
  "requires_branch_selection": false,
  "branches": []
}
```
| Maydon | Izoh |
|---|---|
| `location_type` | `"Toshkent"` yoki `"BTS"` — backend lat/lng'dan aniqlaydi |
| `delivery_fee` | Yetkazish narxi (Toshkent 50 000 / BTS 30 000) |
| `grand_total` | Oldindan jami = `items_total + delivery_fee` (hali saqlanmagan) |
| `requires_branch_selection` | `true` (BTS) → mijoz filial tanlashi SHART. `false` (Toshkent) → to'g'ridan confirm |
| `branches[]` | BTS bo'lsa — mijoz viloyat/tumanidagi filiallar, `distance_km` bilan saralangan. Toshkent bo'lsa `[]` |

> `resolve` **token yopmaydi** — mijoz filialni almashtirsa yoki qayta belgilasa, qayta chaqirsa bo'ladi.

---

### 2.3. `POST /map/{token}/confirm` — 2-qadam (tasdiq) — **token yopiladi**

Mijoz filialni tanlab (BTS) yoki Toshkent bo'lsa to'g'ridan tasdiqlaydi.

**Request body:**
```json
{
  "lat": 39.654,
  "lng": 66.959,
  "bts_branch_id": "0f3c...uuid",
  "address_text": "Samarqand sh., ...",
  "phone": "+998901112233",
  "landmark": "Metro yonida",
  "apartment": "5-uy, 23-xonadon"
}
```
| Maydon | Majburiy | Izoh |
|---|---|---|
| `lat` / `lng` | **HA** | resolve'dagi nuqta bilan bir xil |
| `bts_branch_id` | **BTS bo'lsa HA** | Mijoz tanlagan filial `id` (resolve `branches[].id` dan). Toshkent bo'lsa yubormang. |
| `address_text` | yo'q | Matnli manzil (tavsiya). |
| `phone` / `landmark` / `apartment` | yo'q | Qo'shimcha. |

> BTS'да `bts_branch_id` **majburiy** — yuborilmasa `400`. Toshkent'да e'tiborsiz qoldiriladi.

**Response `200`:**
```json
{
  "order_no": "ORD-260729-EE7220",
  "location_type": "BTS",
  "delivery_fee": 30000.0,
  "items_total": 780000.0,
  "grand_total": 810000.0,
  "address_text": "Samarqand sh., ...",
  "bts_branch": {
    "id": "0f3c...uuid", "name": "SAMARKAND SIYOB", "region": "Samarqand",
    "district": "Samarqand shahar", "address": "...", "landmark": "...",
    "phone": "1230", "work_hours": "...", "lat": 39.6542, "lng": 66.9597
  }
}
```
Toshkent bo'lsa `bts_branch: null`, `delivery_fee: 50000`.

**Muvaffaqiyatdan keyin frontend:**
- Toshkent → "Kuryer manzilingizga yetkazadi. Yetkazish 50 000. Jami {grand_total}."
- BTS → "Buyurtmangiz **{bts_branch.name}** filialiga boradi: {bts_branch.address} (ish vaqti
  {bts_branch.work_hours}). Yetkazish 30 000. Jami {grand_total}."
- Ikkalasида: "Instagram/Telegramга qayting — karta raqamini yuboramiz." (To'lov shu sahifada EMAS.)

---

## 3. Frontend nima qiladi (qadamlar)

1. `/map/{token}` sahifasi + xarita (Yandex/Google/Leaflet — ixtiyoriy).
2. (ixtiyoriy) `GET /map/{token}` — buyurtma summasini ko'rsatish.
3. Mijoz pin qo'yadi / "Mening joylashuvim" (geolocation) → `lat`/`lng`.
4. `POST /map/{token}/resolve { lat, lng }`.
   - `requires_branch_selection = false` (Toshkent) → "50 000, kuryer" ko'rsating, to'g'ridan 6-qadam.
   - `requires_branch_selection = true` (BTS) → `branches[]` ni ro'yxat/dropdown qilib ko'rsating
     (nom + manzil + `distance_km` + ish vaqti). Mijoz birini tanlaydi.
5. Mijoz "Tasdiqlash" bosadi.
6. `POST /map/{token}/confirm { lat, lng, bts_branch_id? , address_text? }`.
   - BTS → tanlangan `bts_branch_id` yuboring. Toshkent → `bts_branch_id` yubormang.
7. Javobни ko'rsating (tasdiq sahifasi) + "chatga qayting".

> Zona va narxni **frontend HISOBLAMAYDI** — faqat lat/lng (va tanlangan filial) yuboradi,
> backend qaytaradi. Bu chalkashlikni oldini oladi.

---

## 4. Xatolar

Barcha xatolar `{"detail": "..."}` (FastAPI standart) + HTTP kod bilan:

| Holat | HTTP | `detail` | Frontend |
|---|---|---|---|
| Token yaroqsiz | `404` | "Checkout linki yaroqsiz" | "Havola yaroqsiz. Sotuvchidan yangi havola so'rang." |
| Link ishlatilgan | `400` | "Bu link allaqachon ishlatilgan" | "Bu havola allaqachon ishlatilgan." |
| Muddati o'tgan | `400` | "Checkout linki muddati o'tgan" | "Havola muddati tugagan. Yangi havola so'rang." |
| lat/lng yo'q | `400` | "Lokatsiya (lat/lng) yuborilishi shart" | Mijozdan joy belgilashni so'rang |
| BTS'да filial tanlanmadi | `400` | "BTS filialini tanlang (bts_branch_id majburiy)" | Ro'yxatdan filial tanlashni so'rang |
| Filial topilmadi | `400` | "Tanlangan BTS filiali topilmadi" | Ro'yxatni yangilang (qayta `resolve`) |

> **Muhim:** `confirm` **bir martalik** — muvaffaqiyatdan keyin token yopiladi. `resolve` ni esa
> qayta chaqirsa bo'ladi (mijoz filialni/joyni almashtirsa). Mijoz butunlay yangi link kerak bo'lsa,
> AI unga yangisini yuboradi.

---

## 5. Backend nima qiladi (kontekst uchun)

1. **Zona:** `lat`/`lng` Toshkent chegara-quti ичida (lat 41.15–41.40, lng 69.10–69.50) →
   `Toshkent`, tashqarida → `BTS`.
2. **BTS filiallar ro'yxati:** mijozga eng yaqin filialdan **viloyat + tuman** aniqlanadi va
   O'SHA tumandagi filiallar masofa bo'yicha qaytariladi. Tumanда kam (< 3) bo'lsa — **butun
   viloyat**. Eng ko'pi 30 ta (eng yaqinlari).
3. **Narx:** Toshkent 50 000 / BTS 30 000 (Settings'дан, admin o'zgartira oladi).
4. **Saqlash (confirm):** `customer_location` (id + type + lat/lng + tanlangan filial);
   `delivery.location_type` + `bts_branch_id`; `order.grand_total = items_total + delivery_fee`;
   buyurtma `waiting_payment` ga o'tadi; token yopiladi.

BTS filiallari (337 ta) `bts_branch` jadvalида, **dinamik** — admin keyin qo'shsa avtomatik
hisobga olinadi (frontend uchun o'zgarish yo'q).

---

## 6. Frontend checklist

- [ ] `/map/{token}` route (SPA sahifa) + xarita.
- [ ] (ixtiyoriy) `GET /map/{token}` — buyurtma xulosasi.
- [ ] Xaritadan `lat`/`lng` → `POST /map/{token}/resolve`.
- [ ] `requires_branch_selection` bo'yicha: BTS → filiallar ro'yxati (nom/manzil/`distance_km`/ish
      vaqti) → tanlash; Toshkent → to'g'ridan tasdiq.
- [ ] `POST /map/{token}/confirm` (BTS'да `bts_branch_id` bilan).
- [ ] Natija sahifasi (Toshkent / BTS filiali + jami narx).
- [ ] Xato holatlari (404/400).
- [ ] Muvaffaqiyatdan keyin "chatga qayting".

**CORS:** `https://almaz-steel.vercel.app` backendда ruxsat etilган.

**Backendда TAYYOR:** `GET /map/{token}`, `POST /map/{token}/resolve`, `POST /map/{token}/confirm`
(va `/checkout/{token}/...` aliaslar), zona aniqlash, filiallar ro'yxati, narx, saqlash, token.
**Frontend QILADI:** map UI, resolve, filial tanlash (BTS), confirm, natijani ko'rsatish.
