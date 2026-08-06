# Buyurtma va Lokatsiya oqimi — to'liq texnik hujjat

> Bu hujjat AI sotuvchi orqali buyurtma qanday rasmiylashishini **boshidan oxirigacha** yozadi:
> xabar kelishi → AI agent → mahsulot → o'lcham/quti → mijoz ma'lumoti → **lokatsiya** → to'lov →
> tasdiqlash → guruhga xabar. Har qadamda qaysi **tool / API / fayl** ishlashini ko'rsatadi.
> Maqsad: hech narsa esdan chiqmasin.

Sana: 2026-08-06 · Model: `gpt-5-mini` (OpenAI) · Til: mijoz tilida, "siz"lab.

---

## 0. Umumiy oqim (xabar qanday AI'ga yetadi)

```
Instagram/Telegram
      │  (mijoz xabar yozadi)
      ▼
POST /webhooks/instagram  yoki  /webhooks/telegram      app/modules/inbox/webhooks.py
      │  1) imzo/secret tekshiruvi (HMAC / X-Telegram-Bot-Api-Secret-Token)
      │  2) SINXRON saqlash: InboxService.ingest_incoming(...)  → Message (DB)
      │  3) best-effort navbat: enqueue_incoming(message.id)
      │  4) tez 200 OK  (xabar YO'QOLMAYDI — 5-invariant)
      ▼
Celery worker:  inbox.process_incoming(message_id)          app/modules/inbox/tasks.py
      ▼
AgentService.handle_incoming_message → Agent.respond(...)   app/modules/ai/agent.py
      │  gating: ai_enabled? paused? closed? test_mode join?
      │  memory + system_prompt + kontekst (buyurtma/IG/do'kon faktlari)
      │  LLM tool-calling sikli (max 16 iteratsiya)  ──►  app/modules/ai/tools.py::dispatch
      │  guardrail (olmos/oltin → serkon/kumush)     ──►  app/modules/ai/guardrail.py
      ▼
Mijozga javob (matn + rasm)  InboxService.ai_send / send_media  →  IG/TG
```

**MUHIM nuqtalar:**
- Guruh/kanal xabarlari **e'tiborsiz** (faqat `chat.type == private`) — `telegram.py::parse_update`.
- Operator yozsa AI **15 daqiqa** (settings `ai_pause_minutes`) pauza — `ai_paused_until`.
- Tool-sikli 16 iteratsiyaдан oshsa → `ai_msg_fallback` + operatorga (kamdan-kam).

---

## 1. Buyurtma bilan bog'liq AI tool'lari

Barchasi `app/modules/ai/tools.py::dispatch` da. LLM'ga `TOOL_SPECS` orqali beriladi.

| Tool | Vazifasi | Natija (asosiy maydonlar) |
|---|---|---|
| `list_categories` | Zaxirada mahsuloti bor kategoriyalar | categories[] |
| `search_product` / `recommend` | Mahsulot topish (matn/byudjet/shortcode) | products[] (`default_variant_id`, `available_sizes`, `engraving`, `warranty`, `resize`, `images`) |
| `get_product_details` | To'liq ma'lumot + `boxes` + `boxes_display` | brief + variants + boxes |
| `send_product_images` | Mahsulot rasmlarini yuboradi (+ karta ostida quti qatori) | {sent, skipped} |
| `send_box_images` | Quti (rang) rasmlarini yuboradi | {sent, skipped} |
| `list_boxes` | Ranglar + narx + `display` (toza format) | {boxes, display} |
| `check_stock` | Variant zaxirasi | available |
| **`create_order`** | **Buyurtma yaratadi + zaxira band qiladi** | order_id, order_no, status, items_total, grand_total |
| `save_customer_name` | Ism va/yoki telefonни saqlaydi | {saved, name, phone} |
| **`request_location`** | **Bir martalik xarita (checkout) linkini yaratadi** | {checkout_url, expires_at} |
| **`set_delivery_address`** | **Manzilni MATN bilan qabul qiladi (xarita shart emas)** | {saved, address, zone, location_type} |
| `get_order_summary` | Jami + dastavka + quti + mijoz ma'lumoti | items[], grand_total, address, has_location |
| `get_order_status` | Buyurtma holati (found/status_text) | {found, order_no, status_text} |
| `get_payment_card` | Asosiy to'lov kartasi | holder_name, card_number_masked |
| `submit_receipt` | Chek RASMINI to'lovga uzatadi | payment_id, status |
| `complete_order` | Buyurtмани "yakunlandi" qiladi (mijoz oldim desa) | order_no, status |
| `handoff_to_operator` | Operatorga o'tkazadi (AI vaqtincha pauza) | status |

---

## 2. To'liq buyurtma ketma-ketligi (9 qadam)

Prompt (`app/modules/ai/prompts.py` → BASE_SYSTEM_PROMPT, "BUYURTMA KETMA-KETLIGI") shu tartibни majbur qiladi.

### 1) Mahsulotni aniqlash
- Mijoz tur so'rasa → `list_categories` → `search_product`/`recommend` → `send_product_images`
  (rasmlar + karta ostida nom/narx/material/tosh/**quti qatori**). "Qaysi biri yoqdi?" deб tanlatadi.
- Mijoz IG post/story link yuborsa → `resolve_instagram_media`.

### 2) O'lcham (faqat uzuk — `requires_ring_size=true`)
- `available_sizes` bo'lsa faqat o'shalarни taklif qiladi (masalan 16, 16.5, 17, 18).
- Mijoz bilmasa → o'rta o'lcham (18) + `resize.available` bo'lsa "zargar o'zgartiradi".

### 3) Rangli quti (MAJBURIY — agar kategoriyada quti bo'lsa)
- Tanlaшдан OLDIN ranglar **narxi bilan** ko'rsatiladi (`list_boxes` `display`): tekin/pulli ajratilgan.
- Mijoz rasm so'rasa → `send_box_images`. Rang tanlansa → keyingi qadamda `create_order`da `box_id`.
- ⚠️ Mijoz allaqachon rang aytган bo'lsa — rasm floodi yo'q, darhol davom.

### 4) BUYURTMA YARATISH — `create_order`
- Argument: `items[{ variant_id (=default_variant_id), quantity, ring_size?, engraving_text?, box_id? }]`.
- `box_id` — **UUID yoki rang NOMI** ("qizil") ham bo'ladi (`_resolve_box_id`).
- Backend: `OrdersService.create_order` (`app/modules/orders/service.py`):
  - Har item uchun **`reserved_qty++`** (zaxira band, TZ 10). `stock_qty` hali kamaymaydi.
  - `order_item.ring_size` (o'lcham order'da, variant emas — 1-invariant).
  - `unit_price` = yaratish vaqtidagi fixed narx; `box_price`, `engraving_price` snapshot.
  - `bonus_snapshot` (global bonus nusxasi). `order_no` unikal.
  - **SUPERSEDE:** yangi order mijozning oldingi faol orderlarini bekor qiladi (bitta faol order).
  - `created_by_ai = True` (KPI uchun).
  - Holat: **`pending`**.

### 5) Mijoz ma'lumotlari (MAJBURIY) — `save_customer_name`
- Ism-familiya + telefon. Bularsiz to'lov/karta bosqichiga O'TILMAYDI.

### 6) LOKATSIYA  ⬅️ **(batafsil 3-bo'limda)**
- Avval **xarita linki** (`request_location`), keyin **matn fallback** (`set_delivery_address`).
- Natija: `delivery` yaratiladi/to'ladi, zona aniqlanadi, order → **`waiting_payment`**.

### 7) Manzil tasdig'i + yetkazish info + KARTA
- Tizim **avtomatik** (lokatsiya olingач) yetkazish ma'lumoti + kartani yuboradi
  (`_send_payment_followup`). Zona: Toshkent → 🚕 Yandex; viloyat → 📮 BTS.
- ‼️ Karta berishdan OLDIN: ism + telefon + lokatsiya — **uchalasi** bo'lishi shart. Yetmasa so'raydi.
- **Yetkazish puli buyurtmaga QO'SHILMAYDI** — mijoz kuryerga/BTS bazasида o'zi to'laydi.
  Bizga faqat mahsulot summasi (prepaid). `grand_total = items_total`, `delivery_fee = 0`.

### 8) Chekni kutish
- Mijoz RASM yuborsa (holat waiting_payment/payment_review) → bu chek: darhol `submit_receipt`.

### 9) Chekni yuborish — `submit_receipt`
- Mijozning oxirgi rasmini oladi (TG getFile / IG url) → MinIO'ga saqlaydi → `PaymentService.submit_payment`.
- Payment → `pending`, order → **`payment_review`**. Owner/manager botiga ✅/❌ tugmalar bilan boradi.

---

## 3. LOKATSIYA qismi — batafsil (eng muhim)

Lokatsiya **IKKI yo'l** bilan olinadi. AI avval xarita linkини beradi, muammo bo'lsa matnга o'tadi.

### Prompt oqimi (AI qanday harakat qiladi)
1. `request_location` chaqiradi → `checkout_url` linkини mijozga yuboradi: *"Manzilingizni shu havola orqali yuboring 📍"*.
2. So'ng so'raydi: *"Lokatsiyani topishда muammo bo'lmayaptimi?"*.
3. Mijoz **muammo bor** desa ("topolmadim/ishlamadi") YOKI "yubordim" desa-yu holat hali `pending` bo'lsa
   (link ishlamagan) → manzilni **MATN** bilan so'raydi → `set_delivery_address`.
4. Mijoz to'g'ridan-to'g'ri manzilni matn bilan yozsa ("Samarqand viloyati Narpay tumani") → link kutmay `set_delivery_address`.

---

### 3.1 Yo'l A — Xarita (checkout) linki

**Qadam A1 — link yaratish** (`request_location` tool → `DeliveryService.create_checkout_link`):
```
app/modules/delivery/service.py::create_checkout_link(order_id)
  - delivery yozuvi bo'lmasa yaratadi (status=awaiting_address)
  - CheckoutToken yaratadi:  token_hash = hash(raw),  expires_at = now + 24h,  used=False
  - link:  {FRONTEND_MAP_URL}/map/{raw_token}     (config: frontend_map_url = almaz-steel.vercel.app)
  - qaytadi: (url, raw_token, expires_at)
```
Token **hash** saqlanadi (raw emas), **bir martalik**, **24 soat** (config `checkout_token_expiry_hours`).

**Qadam A2 — mijoz linkni ochadi** (frontend sahifa, IKKI qadamli, `app/modules/delivery/checkout.py`):

| # | API (public, JWT yo'q) | Vazifa |
|---|---|---|
| 1 | `GET  /map/{token}`          | Kontekst: order_no, items_total, zona narxlari. Token yopilmaydi. |
| 2 | `POST /map/{token}/resolve` `{lat,lng}` | Zona (Toshkent/BTS) + (BTS bo'lsa) eng yaqin filiallar ro'yxati. **Token yopilmaydi.** |
| 3 | `POST /map/{token}/confirm` `{lat,lng, bts_branch_id?, address_text?, phone?}` | Saqlaydi, **token yopiladi**. |

> `/checkout/{token}/...` — bir xil endpointlar (alias). Toshkent bo'lsa filial tanlash yo'q.

**Qadam A3 — confirm backend** (`DeliveryService.confirm_location`):
```
- lat/lng majburiy. is_in_tashkent(lat,lng)? (config bounding-box, geo.py)
    Toshkent → location_type=Toshkent, provider=yandex, zone=tashkent
    tashqarida → location_type=BTS,     provider=bts,    zone=region
- CustomerLocation saqlaydi (lat/lng/type/bts_branch/address_text) — qayta ishlatiladi.
- delivery.* to'ldiriladi, status=ready.  fee = 0 (yetkazish alohida to'lanadi).
- order.delivery_fee = 0;  order.grand_total = items_total.
- order.status:  pending → waiting_payment   (+ OrderStatusHistory)
- token.used = True  (one-time / replay himoya)
```

**Qadam A4 — avtomatik follow-up** (`checkout.py::_send_payment_followup`, confirm ichida chaqiriladi):
```
- ism yoki telefon YO'Q bo'lsa → karta O'RNIGA yetishmagan ma'lumotni so'raydi
   (ai_msg_need_info_before_payment), AI state = awaiting_payment.
- hammasi bo'lsa → mijozga yuboriladi:
   [ai_msg_location_confirmed_head]  "Manzilingiz qabul qilindi ✅"
   [zona matni] ai_msg_delivery_tashkent (Yandex) yoki ai_msg_delivery_bts (BTS)
   [ai_msg_location_confirmed_card]  karta + "chek RASMINI yuboring 📸"
   AI state = awaiting_payment.
```

---

### 3.2 Yo'l B — Matnli manzil (fallback, xarita shart emas)

`set_delivery_address` tool → `DeliveryService.set_text_address` (`delivery/service.py`):
```
- accept_text_address (settings) yoqilgan bo'lishi kerak.
- Faol buyurtmani oladi (order_id ixtiyoriy).
- zone = _zone_from_text(address_text):
     "toshkent/tashkent" bor + "viloyat/tuman" YO'Q → tashkent (Yandex)
     aks holda → region (BTS)
- delivery.address_text, zone, provider, location_type, status=ready, fee=0.
- phone berilса mijoz profiliga ham yoziladi.
- order.delivery_fee = 0;  order.grand_total = items_total.
- order.status:  pending → waiting_payment.
```
Tool dispatch (`tools.py::set_delivery_address`) so'ng **`_send_payment_followup`** ni chaqiradi —
ya'ni matnli manzilда ham avtomatik yetkazish info + karta yuboriladi (Yo'l A bilan bir xil).

> Zona MATNДАН taxminiy — operator baribir tekshiradi. Narx modeli zonaga bog'liq emas
> (yetkazishни mijoz kuryerga/BTS bazasида o'zi to'laydi).

---

## 4. Buyurtma statuslari (hayotiy sikl)

`app/modules/orders/models.py::OrderStatus`

```
draft → pending → waiting_payment → payment_review → confirmed
                                                        → preparing → packed → shipping → delivered → completed
        (istalgan payt) → cancelled / refunded / returned
```

| Status | Qachon | Zaxira ta'siri |
|---|---|---|
| `pending` | `create_order` | `reserved_qty++` |
| `waiting_payment` | lokatsiya olingач (confirm / set_text_address) | — |
| `payment_review` | chek yuborildi (`submit_receipt`) | — |
| **`confirmed`** | **to'lov APPROVED** (`PaymentService.approve`) | **`stock_qty--`, `reserved_qty--`** |
| `cancelled` | bekor / supersede / reject | `reserved_qty--` |
| `completed` | mijoz "oldim" (`complete_order`) | — |

**AI kontekst statuslari** (AI har javobда joriy buyurtмани biladi):
`pending, waiting_payment, payment_review, confirmed, preparing, packed, shipping, delivered`
(`OrdersRepository._CONTEXT_STATUSES`). `completed`/`cancelled` — kontekstга kirmaydi.

---

## 5. To'lov + Owner tasdig'i + Guruh xabari

```
submit_receipt (AI)  →  PaymentService.submit_payment
     payment=pending, order=payment_review
     NotificationService.notify_payment_review → owner Telegram chat (✅/❌ tugmalar)
                                                  settings: payment_review_telegram_chat_id
     │
     ├── ✅ APPROVE:  POST /payments/{id}/approve   (yoki bot tugmasi → callback)
     │      - idempotent (bir marta)
     │      - stock_qty-- , reserved_qty--  (variant/combo + box)
     │      - order → confirmed  (operatorga tushadi)
     │      - Auditlog (payment.approve)
     │      - mijozga: ai_msg_payment_approved  ("operator siz bilan bog'lanadi")
     │      - AI PAUZA: _pause_ai (handoff_pause_minutes) — admin o'zi yakunlaydi
     │      - ⭐ GURUHGA:  NotificationService.notify_order_confirmed(order)
     │             settings: orders_group_telegram_chat_id
     │             matn: № + mahsulot/o'lcham/quti/gravirovka + mijoz + manzil + jami
     │
     └── ❌ REJECT:  POST /payments/{id}/reject
            - reject_reason_required (settings) tekshiruvi
            - reserved_qty--  (band bo'shaydi)
            - mijozga sabab bilan xabar
```

**Guruh xabari MISOLI:**
```
✅ Yangi tasdiqlangan buyurtma
№ ORD-260805-A622C0

• Trio model uzuk, o'lcham 18, quti: Qizil

👤 Ikkinchi Test
📞 998900001122
📍 Samarqand viloyati Payariq tumani (BTS)
💰 Jami: 299 000 so'm
```
Faqat **tasdiqlanганда** yuboriladi. Sozlanmagan bo'lsa (chat_id bo'sh) — jim.

---

## 6. TEST rejimi (ai_test_mode)

`settings.ai_test_mode = true` bo'lsa, AI suhbatга **BIRINCHI** qo'shilganда
(`agent.py::respond`, `_first_ai_message`):
- **Buyurtmasi YO'Q** → ENG AVVAL ogohlantirish (`ai_msg_test_mode_notice`):
  *"Men hozir TEST rejimidaman... buyurtma rasmiylashtirmoqchi bo'lsangiz menga yozing"* → so'ng normal davom.
- **Buyurtmasi BOR** (`get_current_order`) → AI hijack QILMAYDI:
  *"buyurtma jarayonidasiz — adminimiz o'zi yakunlab bog'lanadi"* → `handed_off` + pauza.

**Alohida qoida (admin qo'lда yuritган buyurtma):** mijoz mavjud buyurtma/jo'natma haqида so'rasa
("chiqazdingizmi", "pochta keldi ismni xato yozdingiz", "cheki", "oldim") va `get_order_status`
TOPMASA → AI o'zicha to'qimay **darhol `handoff_to_operator`** ("operatorimiz tekshirib bog'lanadi").

---

## 7. Muhim sozlamalar (settings — CRM'дан boshqariladi)

| Kalit | Vazifa |
|---|---|
| `accept_text_address` | Matnli manzilни qabul qilish (fallback) |
| `delivery_fee_tashkent` / `delivery_fee_region` | Zona narxi (ma'lumot uchun; jamiga qo'shilmaydi) |
| `operator_phone` | AI beradigan operator raqami (bo'sh bo'lsa complaint_phone) |
| `complaint_phone` | Shikoyat/zaxira raqam |
| `store_offline` / `store_pickup_enabled` / `store_address` / `store_work_hours` | Offline do'kon (kelib olish) |
| `ai_test_mode` | Test ogohlantirishi yoqilishi |
| `ai_pause_minutes` (15) | Operator yozgach AI pauzasi |
| `handoff_pause_minutes` (60) | Handoff/approve'дан keyin AI pauzasi |
| `boxes_enabled` | Rangli quti tizimi |
| `engraving_enabled` / `engraving_price` / `engraving_max_chars` | Gravyurka |
| `warranty_enabled` / `warranty_months` / `warranty_text` | Kafolat |
| `resize_enabled` / `resize_price` | O'lcham o'zgartirish |
| `payment_required` | Prepaid majburiy |
| `payment_review_telegram_chat_id` | Chek boradigan owner chat |
| **`orders_group_telegram_chat_id`** | **Tasdiqlangan buyurtма boradigan guruh** |
| `llm_model` (gpt-5-mini) / `ai_temperature` (gpt-5 uchun 1) | LLM |

AI matnlari (`ai_msg_*`, `ai_ctx_*`, `ai_system_prompt`) — `setting` jadvalида (registr:
`app/modules/ai/prompt_registry.py`). Yangilash: `make ai-prompts-seed-force`.

---

## 8. Muhim fayllar

| Fayl | Vazifa |
|---|---|
| `app/modules/inbox/webhooks.py` | IG/TG webhook (imzo → saqlash → navbat → 200) |
| `app/modules/inbox/tasks.py` | Celery `inbox.process_incoming` (AI'ni ishga tushiradi) |
| `app/modules/inbox/channels/{telegram,instagram}.py` | parse/verify/send (rasm/matn/typing) |
| `app/modules/ai/agent.py` | Agent yadrosi: gating, memory, tool-sikli, test-join |
| `app/modules/ai/tools.py` | Barcha AI tool'lari (`dispatch`) |
| `app/modules/ai/prompts.py` | System prompt (BUYURTMA KETMA-KETLIGI shu yerda) |
| `app/modules/ai/prompt_registry.py` | Barcha AI matnlari (DB'дан boshqariladi) |
| `app/modules/ai/guardrail.py` | olmos/oltin → serkon/kumush; prompt injection |
| `app/modules/orders/service.py` | `create_order`, reservation, status, cancel/supersede |
| `app/modules/delivery/service.py` | `create_checkout_link`, `confirm_location`, **`set_text_address`** |
| `app/modules/delivery/checkout.py` | Public `/map/{token}` (resolve/confirm) + `_send_payment_followup` |
| `app/modules/delivery/geo.py` | `is_in_tashkent`, eng yaqin BTS filial |
| `app/modules/payments/service.py` | `submit_payment`, `approve` (+guruh), `reject` |
| `app/modules/notifications/service.py` | Owner chek xabari + **guruh buyurtма xabari** |

---

## 9. Qisqa API ketma-ketligi (bitta buyurtma)

```
1.  POST /webhooks/{telegram|instagram}          ← mijoz xabari (avtomatik)
2.  (AI ichida) create_order                      → order: pending, reserved++
3.  (AI ichida) save_customer_name                → ism/telefon
4.  (AI ichida) request_location                  → checkout_url  (yoki set_delivery_address)
5.  GET  /map/{token}                             ← mijoz sahifani ochadi
6.  POST /map/{token}/resolve  {lat,lng}          → zona/filiallar
7.  POST /map/{token}/confirm  {lat,lng,...}      → delivery ready, order: waiting_payment
        └── _send_payment_followup                → karta + chek so'rovi (avtomatik)
8.  (AI ichida) submit_receipt                    → payment: pending, order: payment_review
        └── owner chatга ✅/❌
9.  POST /payments/{id}/approve                   → order: confirmed, stock--, AI pauza
        └── guruhга tasdiqlangan buyurtма xabari  (orders_group_telegram_chat_id)
```

> Matnli manzил varianti: 4-qadam `set_delivery_address` bo'ladi, 5–7 qadamlar (xarita) tushib qoladi —
> to'g'ridan-to'g'ri `waiting_payment` + karta.

---

*Oxirgi yangilanish: 2026-08-06. Kod bilan sinxron — o'zgartirishда shu hujjatни ham yangilang.*
