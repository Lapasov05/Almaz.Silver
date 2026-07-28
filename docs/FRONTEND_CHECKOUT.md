# Frontend — Location / Checkout (Yandex xarita)

> Migratsiya `0019`. Jonli Postgres smoke: **13/13**. Butun oqim backendda tayyor.
> Frontend Yandex-xaritali **bir sahifa** yasaydi; backend bir martalik token + 2 ta API beradi.

## Oqim (3 qadam)
1. **Bir martalik token** (backend/AI generatsiya qiladi):
   `POST /delivery/orders/{order_id}/checkout-link` (ruxsat: `orders:update`) →
   ```json
   { "url": "https://front.app/checkout/<token>", "token": "<token>", "expires_at": "..." }
   ```
   - `url` — `PUBLIC_BASE_URL` (= **frontend domeni**) + `CHECKOUT_PATH` (`/checkout`) + `/<token>`.
   - `token` — **raw token** (frontend o'z page URL'ini qurishi uchun). Muddatli (24h), **bir martalik**.
   - AI `request_location` tool ham shu linkni mijozga yuboradi.

2. **Sahifa konteksti** (page ochilganda):
   `GET /checkout/{token}` (OCHIQ, token bilan) →
   ```json
   { "order_no": "ORD-...", "items_total": "150000.00",
     "zones": { "tashkent": "50000.00", "region": "30000.00" } }
   ```
   Token yaroqsiz/ishlatilgan/muddati o'tgan → `400/404 {"detail": "..."}`.

3. **Lokatsiyani yuborish** (bir marta):
   `POST /checkout/{token}` (OCHIQ) — body:
   ```json
   {
     "lat": 41.31, "lng": 69.28,
     "address_text": "Chilonzor 12",
     "phone": "+998901112233",
     "landmark": "Metro yonida",         // orientir (mo'ljal)
     "apartment": "5-qavat, 34-xonadon"  // qavat/kvartira/domofon
   }
   ```
   → `DeliveryOut` (zona + narx qo'shilgan). Bundan keyin token **yopiladi** (qayta ishlatib bo'lmaydi),
   buyurtma **`waiting_payment`** ga o'tadi, AI chatda to'lov kartasini beradi.

## Muhim
- **Zona AVTOMATIK**: frontend faqat `lat/lng` yuboradi — backend Toshkent chegara-quti (bounding box)
  ichida bo'lsa **tashkent (50k)**, aks holda **region (30k)** deb belgilaydi. Mijoz zona TANLAMAYDI.
  (Koordinatasiz yuborilsa `zone` fallback ishlatiladi.) Chegara `.env` orqali sozlanadi
  (`DELIVERY_TASHKENT_LAT_MIN/MAX`, `..._LNG_MIN/MAX`).
- **CORS**: `/checkout/*` ochiq (auth yo'q, token himoyasi). Frontend domenini `CORS_ORIGINS` ga qo'shing.
- **Sozlash**: `PUBLIC_BASE_URL=https://<frontend-domen>` , `CHECKOUT_PATH=/checkout` (yoki xohlagan yo'l).

## Frontend TODO
- `/checkout/:token` sahifasi: `GET /checkout/:token` bilan buyurtma xulosasi + zona narxlarini ko'rsatish.
- **Yandex xarita**: mijoz pin qo'yadi → `lat/lng`; (ixtiyoriy) reverse-geocode → `address_text`.
- Form: telefon, orientir, qavat/kvartira. "Yuborish" → `POST /checkout/:token`.
- Muvaffaqiyat: "Lokatsiya qabul qilindi, to'lovga o'ting" (AI chatda davom etadi). Token bir martalik —
  qayta yuborishда `400` (ishlatilgan).

## Tekshirildi: 13/13 (jonli Postgres)
link+raw token+expiry · context (zonalar) · Toshkent lat/lng→auto tashkent+50k+maydonlar ·
order→waiting_payment · bir martalik (replay xato) · viloyat→region+30k · koordinatasiz fallback ·
muddati o'tgan token xato · zone bounding-box helper.
