# Frontend — Lokatsiya (xarita) sahifasi integratsiyasi

> Bu hujjat **frontend dasturchisi** uchun. Almaz AI sotuvchi mijozga buyurtma manzilini
> olish uchun bir martalik **xarita linki** yuboradi. Frontend shu sahifani ko'rsatadi,
> mijozdan lokatsiya oladi va backendga qaytaradi. Backend zonani (Toshkent/BTS) aniqlab,
> narxni hisoblaydi.

**Backend bazaviy URL (prod):** `https://almaz.api.cognilabs.org`
**Frontend map sahifasi:** `https://almaz-steel.vercel.app/map/{token}`

---

## 1. Umumiy oqim

```
AI (Instagram/Telegram) → mijozga link:  https://almaz-steel.vercel.app/map/{token}
        │
        ▼
Frontend  /map/{token}  sahifasi ochiladi
        │  1) GET  {API}/map/{token}   → buyurtma xulosasi + narxlar
        │  2) Mijoz xaritada joyni belgilaydi (lat/lng)
        │  3) POST {API}/map/{token}   { lat, lng, ... }
        ▼
Backend:  lat/lng Toshkentdami? → type=Toshkent (50 000) yoki BTS (30 000 + eng yaqin filial)
        │  → mijoz lokatsiyasi saqlanadi, buyurtmaga narx qo'shiladi, token yopiladi
        ▼
Frontend:  natijani ko'rsatadi (tasdiq): tur, narx, jami, BTS bo'lsa — eng yaqin filial
        │
        ▼
Mijoz Instagram/Telegramga qaytadi → AI karta raqamini yuboradi (bu backend/AI ishi)
```

`{token}` — bir martalik, muddatли (24 soat). Har buyurtma uchun AI yangi link yuboradi.
Mijozda **bir vaqtda faqat bitta faol buyurtma** bo'ladi (yangi buyurtma eskisini bekor qiladi),
shuning uchun token doim to'g'ri buyurtmага tegishli — chalkashlik yo'q.

---

## 2. API kontrakti

### 2.1. `GET /map/{token}` — sahifa konteksti (buyurtma xulosasi)

Sahifa ochilganda chaqiring — buyurtma raqami va zona narxlarini ko'rsatish uchun.

**Request:** header/parametrsiz (token URL'da).

**Response `200`:**
```json
{
  "order_no": "ORD-260729-EE7220",
  "items_total": 780000.0,
  "zones": { "tashkent": 50000.0, "region": 30000.0 }
}
```
| Maydon | Izoh |
|---|---|
| `order_no` | Buyurtma raqami (ko'rsatish uchun) |
| `items_total` | Mahsulotlar summasi (yetkazishsiz) |
| `zones.tashkent` | Toshkent yetkazish narxi (odatда 50 000) |
| `zones.region` | Viloyat (BTS) narxi (odatда 30 000) |

**Xatolar:** `404` — token yaroqsiz; `400` — link ishlatilgan yoki muddati o'tgan
(quyida "Xatolar" bo'limiga qarang).

---

### 2.2. `POST /map/{token}` — lokatsiyani yuborish

Mijoz xaritada joyni belgilagach chaqiring.

**Request body (JSON):**
```json
{
  "lat": 41.311081,
  "lng": 69.279729,
  "address_text": "Toshkent sh., Chilonzor, 12-kvartal",
  "phone": "+998901112233",
  "landmark": "Metro yonida",
  "apartment": "5-uy, 23-xonadon"
}
```
| Maydon | Majburiy | Izoh |
|---|---|---|
| `lat` | **HA** | Kenglik (masalan `41.31`). Zona SHU asosda aniqlanadi. |
| `lng` | **HA** | Uzunlik (masalan `69.27`). |
| `address_text` | yo'q | Matnli manzil (ixtiyoriy, lekin tavsiya etiladi). |
| `phone` | yo'q | Telefon (AI allaqachon olgan bo'lishi mumkin). |
| `landmark` | yo'q | Mo'ljal/orientir. |
| `apartment` | yo'q | Qavat/kvartira/domofon. |

> `lat`/`lng` **majburiy**. Yuborilmasa `400` qaytadi.

**Response `200` — Toshkent misoli:**
```json
{
  "order_no": "ORD-260729-EE7220",
  "location_type": "Toshkent",
  "delivery_fee": 50000.0,
  "items_total": 780000.0,
  "grand_total": 830000.0,
  "address_text": "Toshkent sh., Chilonzor, 12-kvartal",
  "bts_branch": null
}
```

**Response `200` — BTS (Toshkentdan tashqarida) misoli:**
```json
{
  "order_no": "ORD-260729-EE7220",
  "location_type": "BTS",
  "delivery_fee": 30000.0,
  "items_total": 780000.0,
  "grand_total": 810000.0,
  "address_text": "Samarqand sh., ...",
  "bts_branch": {
    "id": "0f3c...uuid",
    "name": "M BARAKA SAM",
    "region": "Samarqand",
    "district": "Samarqand shahar",
    "address": "Samarqand sh, ... ko'chasi, 5-uy",
    "landmark": "... yonida",
    "phone": "1230",
    "work_hours": "Du-Shan: 09:00-18:00; Yak: Dam olish kuni",
    "lat": 39.6542,
    "lng": 66.9597
  }
}
```
| Maydon | Izoh |
|---|---|
| `location_type` | `"Toshkent"` yoki `"BTS"` — backend lat/lng'dan aniqlaydi |
| `delivery_fee` | Yetkazish narxi (Toshkent 50 000 / BTS 30 000) |
| `grand_total` | Jami to'lov = `items_total + delivery_fee` |
| `bts_branch` | **BTS bo'lsa** — mijozga ENG YAQIN filial (u shu yerdan oladi). Toshkent bo'lsa `null`. |

**Frontend natija sahifasi:**
- `location_type = "Toshkent"` → "Kuryer manzilingizga yetkazadi. Yetkazish: 50 000 so'm."
- `location_type = "BTS"` → "Buyurtmangiz **{bts_branch.name}** filialiga boradi. Manzil:
  {bts_branch.address}. Ish vaqti: {bts_branch.work_hours}. Yetkazish: 30 000 so'm."
- Ikkalasida ham: "Jami to'lov: {grand_total} so'm. Instagram/Telegramга qayting — karta
  raqamini yuboramiz." (To'lov karta raqami AI orqali chatда boradi, bu sahifada EMAS.)

---

## 3. Xarita (map) — frontend nima qiladi

1. Sahifa ochilганда `GET /map/{token}` bilan buyurtma xulosasini oling (yoki to'g'ridan
   xaritani ko'rsating).
2. Xarita komponenti (Yandex Maps / Google Maps / Leaflet — ixtiyoringiz) ko'rsating.
   Mijoz **pin** qo'yadi yoki "Mening joylashuvim" (geolocation) tugmasini bosadi.
3. Tanlangan nuqtaning `lat`/`lng` ni oling. (Ixtiyoriy: `address_text`ni reverse-geocoding
   bilan to'ldiring.)
4. "Tasdiqlash" tugmasi → `POST /map/{token}` `{ lat, lng, address_text? }`.
5. Javobni ko'rsating (yuqoridagi natija sahifasi). Muvaffaqiyatdan keyin mijozga
   "chatga qaytish" ko'rsatmasini bering.

> Zona (Toshkent/BTS) va narxni **frontend HISOBLAMAYDI** — faqat lat/lng yuboradi,
> backend qaytaradi. Bu chalkashlikni oldini oladi.

---

## 4. Xatolar

Barcha xatolar `{"detail": "..."}` ko'rinishida (FastAPI standart), tegishli HTTP kod bilan:

| Holat | HTTP | `detail` (taxminan) | Frontend nima qiladi |
|---|---|---|---|
| Token yaroqsiz | `404` | "Checkout linki yaroqsiz" | "Havola yaroqsiz. Iltimos, sotuvchidan yangi havola so'rang." |
| Link ishlatilgan | `400` | "Bu link allaqachon ishlatilgan" | "Bu havola allaqachon ishlatilgan." (bir martalik) |
| Muddati o'tgan | `400` | "Checkout linki muddati o'tgan" | "Havola muddati tugagan. Yangi havola so'rang." |
| lat/lng yuborilmadi | `400` | "Lokatsiya (lat/lng) yuborilishi shart" | Mijozga joy belgilashni so'rang |

> **Muhim:** link **bir martalik**. Muvaffaqiyatli `POST`dan keyin token yopiladi —
> qayta yuborib bo'lmaydi. Agar mijoz qayta kirmoqchi bo'lsa, AI unga **yangi havola**
> yuboradi (backendда yangi token generatsiya bo'ladi).

---

## 5. Backend nima qiladi (kontekst uchun)

1. **Zona aniqlash:** `lat`/`lng` Toshkent shahar chegara-quti ichidami tekshiradi
   (lat 41.15–41.40, lng 69.10–69.50). Ichida → `Toshkent`, tashqarida → `BTS`.
2. **BTS bo'lsa:** DB'dagi **337 ta BTS filiali** ichidan koordinata bo'yicha **eng yaqinini**
   topadi (haversine masofa) va buyurtmага biriktiradi.
3. **Narx:** Toshkent = 50 000, BTS = 30 000 (Settings'дан, admin o'zgartira oladi).
   `order.grand_total = items_total + delivery_fee`.
4. **Saqlash:** mijoz lokatsiyasi `customer_location` jadvalида (id + type + lat/lng + filial)
   saqlanadi; buyurtмага `location_type` yoziladi; buyurtma `waiting_payment` ga o'tadi.
5. **Token:** bir martalik yopiladi.

BTS filiallari `bot_branches.json`dan seed qilinган va **dinamik** — keyin admin API orqali
yangi filial qo'shsa, avtomatik hisobga olinadi (frontend uchun o'zgarish yo'q).

---

## 6. Frontend uchun yig'ma checklist

- [ ] `/map/{token}` route (SPA sahifa).
- [ ] (ixtiyoriy) `GET /map/{token}` — buyurtma xulosasini ko'rsatish.
- [ ] Xarita + pin/geolocation → `lat`/`lng`.
- [ ] `POST /map/{token}` `{ lat, lng, address_text? }`.
- [ ] Javobga qarab natija sahifasi (Toshkent / BTS filiali + jami narx).
- [ ] Xato holatlari (404/400) uchun aniq xabarlar.
- [ ] Muvaffaqiyatdan keyin "chatga qayting" ko'rsatmasi.

**CORS:** `https://almaz-steel.vercel.app` backendда allaqachon ruxsat etilган.

**Backendда TAYYOR:** endpointlar (`GET`/`POST` `/map/{token}` va `/checkout/{token}`),
zona aniqlash, eng yaqin BTS filiali, narx, saqlash, token.
**Frontend QILADI:** map UI, lat/lng olish, POST, natijani ko'rsatish.
