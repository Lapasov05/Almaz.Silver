# Backend — Buyurtma bosqichini o'zgartirish endpoint (Kanban drag-&-drop)

> ✅ **BAJARILDI (2026-07-30):** `POST /orders/{order_id}/status` endpointи qo'shildi va testdan o'tdi.
> Frontend `.env` da `VITE_FEATURE_ORDERS_DND=true` qilishi mumkin — boshqa backend ishi kerak emas.
> Qaror: **A variant** (admin/menejer istalgan o'tishga ruxsat) + `cancelled/refunded/returned`
> `/orders/{id}/cancel` orqali (zaxira bo'shatiladi). Batafsil §2, §4.

> Kim uchun: backend dasturchisi.
> Nima kerak edi: buyurtma statusini qo'lda o'zgartirish (stage transition) endpointi. Ilgari yo'q edi,
> shu sababli Buyurtmalar sahifasidagi Kanban drag-&-drop faqat brauzerda ishlardi — serverga
> saqlanmasdi (sahifani yangilasa, karta eski ustuniga qaytardi).
>
> Frontend bu endpointга allaqachon to'liq ulangan (optimistik yangilash + rollback + toast).

Backend bazaviy URL (prod): https://almaz.api.cognilabs.org

---

## 1. Muammo va tasdiqlangan holat (live probe, 2026-07-29 — endi HAL QILINDI)

> Quyidagi jadval endpoint qo'shilishidan OLDINGI holat. Endi `POST /orders/{id}/status` **mavjud**
> (`orders:update` ruxsati bilan) va §2 dagidek ishlaydi.

Kanban ustundan-ustunga sudralganda status shu endpointга yuborilishi kerak edi, lekin ilgari yo'q edi:

| So'rov | Natija | Xulosa |
|---|---|---|
| POST /orders/{id}/status { "status": "confirmed" } | 404 {"detail":"Not Found"} | Route umuman mavjud emas |
| POST /orders/{id}/cancel (mavjud, taqqoslash uchun) | 404 {"detail":"Buyurtma topilmadi"} | Route bor — faqat buyurtma topilmadi |
| PATCH /orders/{id} | 405 Allow: GET | Buyurtmani tahrirlash ham yo'q (alohida masala, §6) |

Ya'ni generik 404 "Not Found" (route yo'q) vs /cancel`ning aniq "Buyurtma topilmadi"` (route bor) —
farq statusni o'zgartirish route umuman ro'yxatdan o'tmaganini ko'rsatadi.

Hozir yagona haqiqiy status o'zgarishi — `POST /orders/{id}/cancel` (faqat `cancelled`ga).

---

## 2. Kerakli endpoint — `POST /orders/{order_id}/status`

Frontend aynan shuni chaqiradi (src/features/orders/api.ts → setOrderStatus):

POST /orders/{order_id}/status
Authorization: Bearer <access_token>
Content-Type: application/json

{ "status": "confirmed" }

| Maydon | Tur | Majburiy | Izoh |
|---|---|---|---|
| order_id (path) | uuid | HA | Buyurtma id |
| status (body) | enum OrderStatus | HA | Yangi status (quyidagi ro'yxatdan) |

Ruxsat: orders:update (yoki mavjud orders:manage) — admin/menejer rollarida. Ruxsatsiz 403.

Javob `200` — to'liq yangilangan `OrderOut` (frontend javobni cache'ga yozadi):

{
  "id": "d4e5...uuid",
  "order_no": "ORD-260729-EE7220",
  "customer_id": "…",
  "assigned_operator_id": "…",
  "status": "confirmed",
  "items_total": "900000.00",
  "delivery_fee": "30000.00",
  "grand_total": "930000.00",
  "created_at": "2026-07-29T10:00:00Z",
  "items": [ … ],
  "history": [
    { "from_status": "waiting_payment", "to_status": "confirmed",
      "changed_by": "user-uuid", "created_at": "2026-07-29T12:00:00Z" }
  ]
}

Nima qilishi kerak:
1. order.status ni yangi qiymatga o'rnatish.
2. order_status_history ga yozuv qo'shish: from_status (eski), to_status (yangi), changed_by
   (joriy foydalanuvchi), created_at. Frontend history[] ni OrderOut ichida kutadi.
3. To'liq OrderOut qaytarish.

> Idempotent: yangi status eski bilan bir xil bo'lsa — 200 qaytaring (o'zgarishsiz), `history`ga
> yozmasangiz ham bo'ladi. Frontend bir xil ustunga tashlashni allaqachon bloklaydi, lekin xavfsiz bo'lsin.

---

## 3. `OrderStatus` qiymatlari va Kanban ustunlari

Frontenddagi to'liq enum (src/shared/api/types.ts):

draft · pending · waiting_payment · payment_review · confirmed ·
preparing · packed · shipping · delivered · completed ·
cancelled · refunded · returned

Kanban ustunlari → tashlaganda yuboriladigan asosiy status:

| Ustun (UI) | Yuboriladigan status | Ustunga tegishli statuslar |
|---|---|---|
| Yangi | pending | draft, pending |
| To'lov kutilmoqda | waiting_payment | waiting_payment, payment_review |
| Tasdiqlangan | confirmed | confirmed |
| Tayyorlanmoqda | preparing | preparing, packed |
| Yo'lda | shipping | shipping |
| Yakunlangan | delivered | delivered, completed |
| Bekor / qaytarilgan | cancelled | cancelled, refunded, returned |

---

## 4. Transition qoidalari (backend qarori)

Ikki variant bor edi — **A variant tanlandi va amalga oshirildi**:
- ✅ **A (tanlandi, sodda): admin/menejer uchun istalgan → istalgan o'tishга ruxsat** (qo'lda tuzatish
  boardi). Statusni yozadi + history qo'shadi. Board to'liq ishlaydi. `set_status` (orders service).
- B (ishlatilmadi): ruxsat etilgan o'tishlar grafi (qat'iy). Kerak bo'lsa keyin qo'shsa bo'ladi
  (noto'g'ri o'tishда 400 + `{"detail":"<sabab>"}`).

> ✅ **`cancelled` qarori (amalga oshirildi):** `POST /orders/{id}/status` `cancelled/refunded/returned`
> ni **qabul qilmaydi** → `400 {"detail":"Bekor/qaytarish uchun /orders/{id}/cancel ishlating (zaxira
> bo'shatiladi)"}`. Frontend «Bekor» ustuniga tashlaganда **`POST /orders/{id}/cancel`** chaqirsin (u
> zaxirani bo'shatadi). Qolgan barcha statuslar `/status` orqali.

---

## 5. Xatolar

| Holat | HTTP | detail |
|---|---|---|
| Buyurtma topilmadi | 404 | "Buyurtma topilmadi" |
| Noto'g'ri status qiymati | 422 | FastAPI validatsiya (enum) |
| Ruxsat etilmagan o'tish (B varianti) | 400 | matnli sabab |
| Ruxsat yo'q | 403 | orders:update kerak |
| Token yo'q/eskirgan | 401 | — |

---

## 6. Bog'liq (ixtiyoriy, alohida) — PATCH /orders/{order_id}

Hozir 405 Allow: GET. Buyurtmani tahrirlash (mijoz, qatorlar, o'lcham, narx, izoh) shu endpointни kutadi
va frontendда VITE_FEATURE_ORDER_EDITING flagi ortида tayyor turibdi. Drag-&-drop uchun shart emas —
faqat kelajak uchun eslatma.

Kutilayotgan shakl: PATCH /orders/{id} { status?, notes?, customer_id?, items?, ring_size?, … } →
OrderOut.

---

## 7. Frontend tomoni (siz uchun kontekst — o'zgartirish kerak emas)

- POST /orders/{id}/status allaqachon ulangan: setOrderStatus() + useSetOrderStatus()
  (optimistik yangilash, xatoда rollback + toast).
- Kanban board FEATURES.ordersKanbanDnd flagi ortида. Endpoint chiqishi bilan:
  `.env` da `VITE_FEATURE_ORDERS_DND=true` — tamom.
- Test: bir buyurtmани ustundan-ustunga sudrab, sahifani yangilang — status saqlanib qolishi kerak;
  order.history ga yangi yozuv qo'shilishi kerak.

Qisqacha (BAJARILDI): `POST /orders/{order_id}/status { status }` → yangilangan `OrderOut`; statusни
yozadi + history qo'shadi; ruxsat `orders:update`; `cancelled/refunded/returned` → `/cancel` (400 bilan
yo'naltiradi); idempotent (bir xil status → 200, history yozilmaydi). Testdan o'tgan (jonli Postgres).

---

# AI promtlar — koddan emas, DATABASE'dan boshqariladi (2026-07-31)

Barcha sun'iy intellekt matnlari (system prompt, kontekst shablonlari, tayyor xabarlar) endi bitta
**registrda** (`app/modules/ai/prompt_registry.py`) va **settings jadvalida** (DB). Kod DOIM
`get_ai_text(db, key, **fmt)` orqali o'qiydi: avval DB, bo'lmasa registr standarti (fallback). Ya'ni
prodda promtlarни DB'dan (settings API) tahrirlaysiz — kodga tegmasdan.

## Prodda ishga tushirish (bir marta)
```bash
make ai-prompts-seed          # 16 promtni DB'ga yozadi (idempotent — mavjudini o'zgartirmaydi)
                              # har biri MAQSAD + QAYERDA ishlatilishi bilan chiqadi
make ai-prompts-seed-force    # registr standarti bilan QAYTA yozadi (DB tahrirlar yo'qoladi)
```
Tahrirlash: `PUT /settings/{key}` `{ "value": "..." }` (kalitlar quyida). Seed shart emas — seed
qilinmasa kod registr standartини ishlatadi (AI baribir ishlaydi); seed faqat DB'dan tahrirlash uchun.

## Barcha AI promt kalitlari (maqsad + qayerda)
| Kalit (settings) | Maqsad | Qayerda ishlatiladi |
|---|---|---|
| `ai_system_prompt` | Asosiy sotuvchi system prompt (rol, qoidalar, oqim) — har javobga | agent.py::respond |
| `ai_greeting_text` | Birinchi salom (LLM yo'q rejimda) | agent.py::respond |
| `ai_ctx_order` | Faol buyurtma konteksti shabloni (xotira/follow-up) | agent.py::_active_order_context |
| `ai_ctx_order_guide_pending` | Buyurtma pending — keyingi qadam | agent.py::_active_order_context |
| `ai_ctx_order_guide_waiting_payment` | Manzil bor, to'lov kutilmoqda — keyingi qadam | agent.py::_active_order_context |
| `ai_ctx_order_guide_payment_review` | Chek tekshirilmoqda — keyingi qadam | agent.py::_active_order_context |
| `ai_ctx_order_guide_default` | Boshqa holat — umumiy ko'rsatma | agent.py::_active_order_context |
| `ai_ctx_order_receipt_hint` | Rasm = chek ekani eslatmasi | agent.py::_active_order_context |
| `ai_ctx_instagram_found` | IG mahsulot topildi — grounding | agent.py::_instagram_context |
| `ai_ctx_instagram_tip_instock` | IG mahsulot zaxirada bor | agent.py::_instagram_context |
| `ai_ctx_instagram_tip_outstock` | IG mahsulot zaxirada yo'q | agent.py::_instagram_context |
| `ai_ctx_instagram_not_found` | IG mahsulot topilmadi — odamdek uzr | agent.py::_instagram_context |
| `ai_msg_fallback` | Bajara olmaganda → operator | agent.py::respond |
| `ai_msg_location_confirmed_head` | Manzil tasdiqlandi + summa (auto) | checkout.py::_send_payment_followup |
| `ai_msg_location_confirmed_card` | To'lov kartasi + chek so'rovi | checkout.py::_send_payment_followup |
| `ai_msg_location_confirmed_nocard` | Karta yo'q — vaqtinchalik xabar | checkout.py::_send_payment_followup |

> Shablonlardagi `{o'rin}`lar (masalan `ai_ctx_order` da `{order_no} {grand_total} {guide}`) kod
> tomonidan to'ldiriladi — tahrirlaganда o'sha nomlarni saqlang. `ai_system_prompt` ni `.format`
> QILMAYDI, shuning uchun undagi `{months}` kabi misollar xavfsiz. To'liq ro'yxat va standart
> qiymatlar: `app/modules/ai/prompt_registry.py`.

> Eslatma: eski `system_prompt_override` sozlamasi hali ham ishlaydi (to'ldirilsa `ai_system_prompt`dan
> ustun keladi) — moslik uchun.

## AI Promtlarni boshqarish API (FRONTEND uchun)

Frontend promt-editor sahifasi shu 4 endpointни ishlatadi. Bazaviy URL: `https://almaz.api.cognilabs.org`.
Auth: `Authorization: Bearer <access_token>`. Ruxsatlar: o'qish `ai:view`, tahrirlash `ai:edit_prompt`.

> Nega alohida (nega oddiy `/settings` emas): bu endpoint har promt bilan birga METAMA'LUMOTni
> (maqsad, qayerda ishlatiladi, o'rinlar, standart qiymat) qaytaradi — editorda "bu promt nima
> qiladi" ko'rinib tursin. Promtlar oldindan belgilangan ro'yxat (16 ta) — yangi qo'shish/o'chirish yo'q,
> faqat **tahrirlash** va **standartga qaytarish**.

### `AiPromptOut` (javob obyekti)
```json
{
  "key": "ai_msg_fallback",
  "purpose": "AI tool-sikli tugab... operatorga o'tkaziladi",   // NIMA UCHUN
  "used_in": "app/modules/ai/agent.py::respond (sikl tugagani)", // QAYERDA
  "placeholders": "",                    // shablon o'rinlari (masalan "{order_no} {grand_total}"); bo'lsa saqlang
  "default_value": "Kechirasiz, ...",    // registr standarti (reset shunga qaytaradi)
  "current_value": "Kechirasiz, ...",    // hozir amalda (DB'da bo'lsa o'sha, aks holda default)
  "is_overridden": false                 // true = tahrirlangan (default emas)
}
```

### 1) Barcha promtlar ro'yxati — `GET /ai/prompts`
Ruxsat: `ai:view`. Javob `200`: `AiPromptOut[]` (16 ta). Editor ro'yxatini shu bilan chizasiz
(har qatorda `key` + `purpose`; `is_overridden=true` bo'lsa "tahrirlangan" belgisi).

### 2) Bitta promt — `GET /ai/prompts/{key}`
Ruxsat: `ai:view`. Javob `200`: bitta `AiPromptOut`. Kalit registrda yo'q → `404 {"detail":"AI promt topilmadi: {key}"}`.

### 3) Tahrirlash — `PUT /ai/prompts/{key}`
Ruxsat: `ai:edit_prompt`. Body: `{ "value": "yangi matn" }` (`value` bo'sh bo'lmasin — `min_length=1`).
Javob `200`: yangilangan `AiPromptOut` (`current_value` = yangi, `is_overridden=true`). Kalit yo'q → `404`.
Bo'sh `value` → `422`.

> **Placeholder ogohlantirishi (MUHIM):** agar `placeholders` bo'sh bo'lmasa (masalan `ai_ctx_order`:
> `{order_no} {products} {grand_total} ...`) — tahrirda o'sha `{nom}`larni AYNAN saqlang, kod ularni
> to'ldiradi. Yo'qotsangiz kontekst noto'g'ri chiqadi (lekin tizim buzilmaydi — mos kelmasa xom matn beriladi).
> `ai_system_prompt` bundan mustasno — u `.format` QILINMAYDI, ichidagi `{months}` kabi misollar xavfsiz.

### 4) Standartga qaytarish — `POST /ai/prompts/{key}/reset`
Ruxsat: `ai:edit_prompt`. Body yo'q. DB'dagi tahrirni o'chiradi → `current_value` registr standartiga qaytadi
(`is_overridden=false`). Javob `200`: `AiPromptOut`. Kalit yo'q → `404`.

### Xatolar
| Holat | HTTP | detail |
|---|---|---|
| Kalit registrda yo'q | 404 | "AI promt topilmadi: {key}" |
| Bo'sh value (PUT) | 422 | FastAPI validatsiya |
| Ruxsat yo'q | 403 | `ai:view` / `ai:edit_prompt` kerak |
| Token yo'q/eskirgan | 401 | — |

### Tavsiya etilgan frontend oqimi
1. `GET /ai/prompts` → ro'yxat (kalit + maqsad; tahrirlanganlarni belgila).
2. Qatorni bosganda `current_value` ni textarea'da ko'rsat + `purpose`/`used_in`/`placeholders` ni yon panelда.
3. **Saqlash** → `PUT /ai/prompts/{key}`. **Standartga qaytarish** → `POST /ai/prompts/{key}/reset`
   (avval `default_value` bilan taqqoslab, "o'zgargan" tugmasini faollashtir).
4. O'zgarish darhol kuchga kiradi — keyingi AI javobi yangi matnni ishlatadi (deploy shart emas).