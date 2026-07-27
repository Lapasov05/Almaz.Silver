# Frontend uchun o'zgarishlar — 2026-07-27

> Bugun backend'ga qo'shilgan/o'zgargan hamma narsa. Har biri jonli Postgres'da testlangan.
> Frontend shu hujjat bo'yicha moslanadi.

## Umumiy qoidalar
- **Auth:** `Authorization: Bearer <access_token>`. Ruxsatlar: box → `products:*`, buyurtma → `orders:*`,
  AI → `ai:override_ai`, integrations → `settings:manage_integrations`.
- **Pagination:** barcha ro'yxat (GET) `{ "items": [...], "total": N, "limit": L, "offset": O }` qaytaradi.
  So'rov: `?limit=&offset=`.
- **Narxlar:** string/number `Numeric(12,2)` (masalan `"5000.00"`). Pul birligi — **UZS**.
- **Xatolar:** `4xx` + `{ "detail": "<xabar>" }`.

---

## 1. 📦 Box (rangli quti) — YANGI

Har **kategoriya** o'z rang qutilariga ega (dynamic). Har rang: alohida narx (`0 = tekin`) + alohida zaxira (count).
Boshqaruv **«kategoriya bo'limi»**da. Buyurtmada har mahsulotga ixtiyoriy 1 box qo'shiladi.

### 1.1. BoxOut (javob obyekti)
```json
{
  "id": "uuid",
  "category_id": "uuid",
  "name_uz": "Qizil",
  "name_ru": null,
  "color_hex": "#E53935",
  "price": "5000.00",
  "is_free": false,
  "stock_qty": 10,
  "reserved_qty": 2,
  "available": 8,
  "is_active": true,
  "sort_order": 0,
  "created_at": "2026-07-27T12:00:00Z"
}
```
- `is_free` — `price == 0` (tekin quti).
- `available = stock_qty - reserved_qty` — mijozga taklif qilinadigan haqiqiy son.

### 1.2. Endpointlar (kategoriya bo'limida boshqaruv)
| Method | Path | Body | Javob |
|---|---|---|---|
| GET | `/catalog/categories/{category_id}/boxes?only_active=&limit=&offset=` | — | `Page[BoxOut]` |
| POST | `/catalog/categories/{category_id}/boxes` | `BoxCreate` | `BoxOut` |
| GET | `/catalog/boxes/{box_id}` | — | `BoxOut` |
| PATCH | `/catalog/boxes/{box_id}` | `BoxUpdate` | `BoxOut` |
| DELETE | `/catalog/boxes/{box_id}` | — | `204` (soft delete) |
| POST | `/catalog/boxes/{box_id}/stock` | `{ "stock_qty": 12 }` yoki `{ "delta": -1 }` | `BoxOut` |

**BoxCreate** (rang qo'shish):
```json
{ "name_uz": "Qizil", "name_ru": null, "color_hex": "#E53935", "price": 5000, "stock_qty": 10, "is_active": true, "sort_order": 0 }
```
- `price` default `0` (tekin). `name_uz` majburiy. Boshqalari ixtiyoriy.

**BoxUpdate** — hammasi ixtiyoriy: `name_uz, name_ru, color_hex, price, is_active, sort_order`.

**Stock (count) boshqaruvi:** `stock_qty` (mutlaq qiymat) yoki `delta` (±). Masalan `{"delta": -1}` bittaga kamaytiradi.

### 1.3. Buyurtmada box (POST `/orders`)
So'rovда har item'ga **ixtiyoriy** `box_id`:
```json
{
  "customer_id": "uuid",
  "items": [
    { "variant_id": "uuid", "quantity": 2, "ring_size": "18", "engraving_text": "Ali", "box_id": "uuid" }
  ]
}
```
Qoidalar (server tekshiradi, buzilса `400 detail`):
- `box_id` **shu mahsulot kategoriyasiga** tegishli bo'lishi shart → aks holда `"Box bu mahsulot kategoriyasiga tegishli emas"`.
- Box zaxirasi yetarli bo'lsin → `"Box zaxirasi yetarli emas (...)"`.
- Global o'chiq bo'lsa → `"Box (quti) xizmati hozircha o'chirilgan"`.

**OrderItemOut** (buyurtma javobida) yangi maydonlar:
```json
{ "...": "...", "box_id": "uuid|null", "box_price": "5000.00", "box_label": "Uzuklar — Qizil" }
```
- `box_price` — buyurtma vaqtidagi **snapshot** (keyin box narxi o'zgarsa, eski buyurtma o'zgarmaydi).
- `box_label` — ko'rsatish uchun "Kategoriya — Rang" nusxasi.
- **Jami:** `items_total += (unit_price + engraving_price + box_price) × quantity`.

### 1.4. Global sozlama
`boxes_enabled` (Settings, bool). O'chirilsa AI/buyurtma box qabul qilmaydi.
`GET /settings/boxes_enabled` · `PUT /settings/boxes_enabled` (mavjud settings API).

### 1.5. Frontend TODO (box)
- **Kategoriya sahifasi**: ranglar ro'yxati (swatch = `color_hex`), qo'shish/tahrirlash/o'chirish, count (`stock_qty`) inline tahrir, `price` (`0` → "Tekin" belgisi).
- **Buyurtma/checkout**: mahsulot kategoriyasidagi mavjud (`available>0`) ranglardan tanlash; tanlangan box narxini jami hisobga qo'shish.
- AI chatda AI o'zi rang taklif qiladi (backend), frontend faqat natijani ko'rsatadi.

---

## 2. 🤖 AI operator override — YANGI

Operator "AI javob bersin" desa — **pauza/handoff/o'chirilgan** holatда ham AI'ni qaytaradi.

| Method | Path | Javob |
|---|---|---|
| POST | `/ai/conversations/{conversation_id}/respond?force=true` | `AgentRespondOut` |

- `force=true` → `ai_paused_until` tozalanadi, `ai_enabled=true` qilinadi, darhol javob beradi.
- `force` yo'q → eski xulq (pauzada `status: "skipped"`).
- Global `ai_enabled` (kill-switch) va yopiq suhbat baribir hurmat qilinadi.

**AgentRespondOut:**
```json
{
  "status": "replied | skipped",
  "reason": "llm_error: ... | operator_handoff | ai_disabled | null",
  "reply": "javob matni | null",
  "message_id": "uuid | null",
  "used_tools": ["search_product", "list_boxes"],
  "violations": [],
  "state": "browsing"
}
```
- `status="skipped"` bo'lsa `reason`ni ko'rsating (masalan `llm_error: ...` — LLM sozlanmagan).

**Frontend TODO:** suhbat oynasida "AI'ni qaytarish / AI javob bersin" tugmasi → shu endpoint `force=true` bilan.

---

## 3. 🔌 Integrations (DB'dan tokenlar) — admin sozlamalar sahifasi

Tokenlar endi **DB'da** (`.env` emas) — API orqali almashtiriladi, deploy shart emas. Ruxsat: `settings:manage_integrations`.

| Method | Path | Izoh |
|---|---|---|
| GET | `/integrations/configs?provider=telegram` | ro'yxat (pagination) |
| POST | `/integrations/configs` | `{provider, key, value, is_active}` — `(provider,key)` upsert |
| PATCH | `/integrations/configs/{id}` | `{value?, is_active?}` |
| DELETE | `/integrations/configs/{id}` | o'chirish |
| GET | `/integrations/events?provider=&status=` | kelgan webhook payload auditi (pagination) |
| POST | `/integrations/telegram/set-webhook` | `{url}` |
| GET | `/integrations/telegram/webhook-info` | ulanish holati |
| GET | `/integrations/telegram/me` | qaysi bot |
| POST | `/integrations/telegram/delete-webhook` | — |
| POST | `/integrations/instagram/subscribe` | IG akkauntni webhookka obuna (majburiy) |

**Kalitlar (`provider/key`):** `telegram/bot_token`, `telegram/webhook_secret`, `instagram/access_token`,
`instagram/business_id`, `instagram/verify_token`, `instagram/app_secret`, `openai/api_key`, `openai/base_url`.

**IntegrationConfigOut:** `{ id, provider, key, value, is_active, created_at, updated_at }`
(`value` — sezgir, faqat `manage_integrations` ruxsatiga ko'rinadi).

**Frontend TODO:** "Integratsiyalar" sozlamalar sahifasi — har provider tokenlarini kiritish/tahrirlash,
Telegram webhook holati (`webhook-info`), Instagram "Subscribe" tugmasi, kelgan eventlar jurnali (`events`).

> ⚠️ **`openai/base_url` ni bo'sh qo'ymang** — bo'sh bo'lsa OpenAI SDK URL'ni buzadi. Kerak bo'lmasa qatorni umuman qo'ymang/o'chiring.

---

## 4. Backend-ichki (frontend uchun ish YO'Q)
Bular faqat serverда — API shakli o'zgarmagan:
- **"Yozyapti..." + 3s pauza** — AI xabar kelgach typing ko'rsatib, ~3s dan keyin javob beradi (kanal ichida).
- **Worker/metadata fix** — AI avtomatik javobi endi ishlaydi (FK xatosi tuzatildi).
- **Instagram tuzatishlar** — `graph.instagram.com`, `business_id`, `message.external_id` uzun ID (500 fix),
  webhook URL oxirida `/` bilan ham ishlaydi, imzo rad etilса audit.
- **OPENAI env** — `.env`dan `OPENAI_API_KEY`/`OPENAI_BASE_URL` olib tashlandi (DB'dan keladi).

---

## Demo ma'lumot (test uchun)
```bash
make demo-seed      # kategoriyalar + mahsulotlar
make demo-boxes     # har kategoriyaga 6 rang (2 tekin + 4 pulli) + boxes_enabled=true
```

## Tekshirildi (jonli Postgres)
Box: **22/22** — CRUD · order reservation/narx/label · to'lov approve(stock--)/reject(release) ·
AI (list_boxes, get_product_details boxes, create_order box_id) · soft delete · demo (idempotent).
