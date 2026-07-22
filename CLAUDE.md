# CLAUDE.md — Almaz AI Seller + CRM

> Bu fayl har sessiyada kontekstni saqlash uchun. To'liq spetsifikatsiya:
> [`TZ_zargarlik_ai_seller_crm.md`](./TZ_zargarlik_ai_seller_crm.md). Implement tartibi — TZ 17-bo'lim (fazalar).

## Loyiha nima
Instagram/Telegram DM orqali kelgan mijozlarni **AI sotuvchi** avtonom sotuvga
olib boradigan single-tenant CRM. Brend: **almazsilver**. Faqat Kumush 925 + rodiy,
tosh — **serkon (CZ)**. Operator faqat tasdiqlangan buyurtmani jo'natadi.

## Stack
- **Backend:** FastAPI (Python 3.12), async
- **DB:** PostgreSQL 16 + pgvector, SQLAlchemy 2.0 (async/asyncpg), Alembic
- **Cache/rate-limit:** Redis
- **Queue:** RabbitMQ + Celery
- **Storage:** MinIO (S3-mos)
- **Auth:** JWT + refresh, parol argon2 (passlib)
- **Infra:** Docker Compose (api, worker, postgres, redis, rabbitmq, minio, nginx)
- **Arxitektura:** Modulli Monolit — har modul `router → service → repository → models`

## Konvensiyalar
- **Kod identifikatorlari inglizcha, izohlar/docstring o'zbekcha** (TZ uslubi).
- Type-hinted, async. DB kirish faqat repository'da; biznes logika service'da; endpoint router'da.
- **DI** orqali bog'lash (`app/core/deps.py`). Yangi modul routeri `app/main.py`'ga qo'shiladi.
- **Yangi model** qo'shilganда `migrations/env.py`'ga import qo'shiladi (metadata uchun).
- Secretlar faqat `.env` (config: `app/core/config.py`, pydantic-settings). Kodda hardcode yo'q.
- Domen xatolari: `AppError`/`AuthError`/`PermissionDenied`/`NotFoundError` (`app/core/exceptions.py`).
- **UUID PK + created_at/updated_at** hamma jadvalда (`app/core/base_model.py` mixinlari).
- Soft delete (`deleted_at`) faqat: product, variant, customer, user (TZ 6.1).
- RBAC: `Depends(require_permission("resource:action"))`. Permission'lar Redis'da keshlanadi.

## Kritik invariantlar (TZ 18-bo'lim) — har fazada saqlanadi
1. **O'lcham variant EMAS** → `order_item.ring_size`; hamma o'lcham bir narx.
2. **Zaxira variant ichida** (`stock_qty`/`reserved_qty`), `available = stock_qty − reserved_qty`.
3. **Bonuslar global** (Settings `bonus_items`), har tovarga emas.
4. **Guardrail (AI):** doim "serkon toshi" / "Kumush 925 + rodiy" / katalogdagi fixed narx.
   AI hech qachon "olmos/diamond" demaydi, narx o'ylab topmaydi/savdolashmaydi.
5. **Prepaid majburiy** (Settings); to'lov tasdiqlanmaguncha jo'natilmaydi; `reviewed_by` javobgar.
6. **Yetkazish zona fixed:** Toshkent 50k / viloyat 30k. Yandex API yo'q.
7. **15-daqiqa AI pauzasi** operator yozgach (`ai_paused_until`).
8. **Til:** mijoz tilida, "siz"lab.

---

## FAZA HOLATI (TZ 17-bo'lim)

### ✅ Faza 0 — Poydevor (TUGADI)
- Modulli FastAPI skeleti: `app/core/` + `app/modules/` (identity, settings to'liq; qolgan 10 modul bo'sh skelet).
- Docker Compose: api, worker, postgres(+pgvector), redis, rabbitmq, minio, nginx.
- `.env.example` + `app/core/config.py` (pydantic-settings).
- Alembic async + migratsiya `0001_phase0_foundation` (pgvector ext + RBAC + setting jadvallari).
- JWT+refresh auth: `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`.
- RBAC skeleton: user/role/permission/role_permission/user_role + `require_permission` dependency + Redis permission cache.
- `setting` jadvali + boshlang'ich sozlamalar (`app/modules/settings/defaults.py`, TZ 14-bo'lim).
- Seed: `app/seed.py` (Super Admin + 15 system rol + permission'lar + settings, idempotent).
- **Tayyor mezoni:** servislar ko'tariladi, login ishlaydi, permission tekshiruvi bor. ✔

**Faza 0 qarorlari (kelajakda e'tibor bering):**
- Refresh token **stateless** (JWT ichida `type=refresh`), rotatsiya bilan. Revocation/blacklist — keyingi fazada Redis bilan.
- RBAC matritsasi TZ 13-bo'lim namunasi asosida seed qilingan; **to'liq sozlanadigan matritsa + custom rol UI — Faza 6**.
- `variant`, `order`, `message` va boshqa jadvallar **hali yo'q** — tegishli fazalarда yaratiladi.
- api container startда migratsiya+seed'ni o'zi bajaradi (dev qulayligi). Prod'da alohida qadam qilinadi.

### ✅ Faza 1 — Katalog + zaxira (TUGADI)
- Modellar: `category`, `product`, `variant`, `product_media` (`app/modules/catalog/models.py`).
- Migratsiya `0002_catalog`: jadvallar + **generated `search_vector` tsvector (GIN)** + **pgvector `embedding` (hnsw, vector_cosine_ops)** + unique/FK indekslar.
- Admin CRUD (RBAC bilan): kategoriya, mahsulot, variant, media — `/catalog/*` (router/service/repository).
- **3 qatlamli qidiruv (TZ 8):** (1) SKU/barcode aniq → (2) IG shortcode lookup → (3) tsvector `websearch_to_tsquery('simple')`. Semantik (pgvector) alohida endpoint.
- **IG shortcode mapping (TZ 7.5):** URL → shortcode ajratish (`catalog/search.py`), `product_media.shortcode` UNIQUE lookup.
- Zaxira variant ichida: `stock_qty`/`reserved_qty`, `available` property; stock adjust endpoint.
- **Tayyor mezoni:** mahsulot qo'shiladi/topiladi (SKU, matn, IG link, embedding bo'yicha). ✔ (jonli Postgres'da smoke test bilan tasdiqlangan)

**Faza 1 qarorlari:**
- `search_vector` — DB generated column (nom+tavsif+ai_keywords, 'simple' config; maxsus o'zbek lug'ati Faza 7).
- Default variant: mahsulot yaratilganда variant berilmasa, 1 ta auto-SKU bilan yaratiladi (TZ muhim qaror 1).
- Enum'lar VARCHAR+CHECK (`native_enum=False`) — migratsiya oddiy.
- **Embedding _generatsiyasi_ (OpenAI) hali yo'q** — Faza 3 (AI). Faza 1'da faqat saqlash+qidiruv mexanizmi (`POST /catalog/search/semantic` embedding qabul qiladi).
- Narx `Numeric(12,2)`. `material`/`stone` default guardrail qiymatlari ("Kumush 925 + rodiy" / "serkon").

### ✅ Faza 2 — Inbox + integratsiyalar (TUGADI)
- Modellar: `customer`, `conversation`, `message` (`app/modules/inbox/models.py`) + migratsiya `0003_inbox` (UNIQUE `(channel, external_id)`, indekslar TZ 6.3: `message(conversation_id, created_at)`, `conversation(status, last_activity_at)`).
- **Webhook ingestor** (`inbox/webhooks.py`, OCHIQ + imzo): `POST /webhooks/telegram` (secret token), `GET/POST /webhooks/instagram` (verify challenge + `X-Hub-Signature-256` HMAC). Oqim: imzo→sinxron saqlash→best-effort navbat→200 OK (TZ 5: xabar yo'qolmaydi).
- **Kanal adapterlari** (`inbox/channels/`): `telegram.py` (parse/verify/send), `instagram.py` (parse/verify/challenge/send), `factory.py`. Outbound `httpx` bilan.
- **Inbox CRM API** (`inbox/router.py`, RBAC): conversations list/get, messages list, **operator send**, mark-read, transfer, assign.
- **15-daqiqa AI pauzasi:** operator yozsa `conversation.ai_paused_until = now()+ai_pause_minutes` (settings'dan) — TZ 9.
- **Celery inbound** `inbox/tasks.py` — STUB (`inbox.process_incoming`), AI oqimi Faza 3'da ulanadi. `enqueue_incoming` best-effort (broker yo'q bo'lsa 200 OK buzilmaydi).
- **Tayyor mezoni:** IG/TG'dan xabar kelib inbox'da ko'rinadi, javob yuboriladi. ✔ (jonli Postgres + ASGI smoke: imzo/ingest/operator-send/handoff)

**Faza 2 qarorlari:**
- Enumlar `VARCHAR` (Pydantic validatsiya) — inbox uchun DB CHECK'siz (qiymatlar app nazoratida).
- **Operator javobi inline yuboriladi** (interaktiv, past kechikish); AI javoblari (Faza 3) Celery worker orqali ketadi. Kanal klient qayta ishlatiladi.
- Token/secret yo'q dev'da: `verify_*` o'tkazib yuboradi, outbound `ChannelError`→`delivery_status=failed` (xabar baribir saqlanadi).
- `celery_task_always_eager` (env) — test/dev broker'siz. Prod'da `false` (RabbitMQ).
- Voice→transkripsiya, xabar dedup (external_id) — keyingi bosqichlarга qoldirildi.
- `.dockerignore` qo'shildi: `.env` va h.k. image'ga tushmaydi (runtime env_file).

### ✅ Faza 3 — AI Agent (yadro) (TUGADI)
- **`ai` moduli:** `knowledge_base` modeli + migratsiya `0004_knowledge` (tsvector GIN + pgvector hnsw). Seed: 6 boshlang'ich KB yozuvi.
- **Guardrail (TZ 15, KRITIK)** — `ai/guardrail.py`: har AI javobi yuborishdan oldin tekshiriladi. "olmos/diamond/brilliant/tabiiy tosh"→"serkon toshi", "oltin/gold"→"Kumush 925 + rodiy". Buzilish qayd etiladi. `sanitize_user_input` (prompt injection).
- **Prompt Manager** — `ai/prompts.py`: versiyalangan system prompt (`settings.prompt_version` + `system_prompt_override`), rol/til/guardrail qoidalari.
- **Memory (TZ 7.3)** — `ai/memory.py`: qisqa muddat (oxirgi N xabar) + uzoq muddat (mijoz profili).
- **State machine (TZ 7.1)** — `ai/state_machine.py`: greeting→...→closed o'tishlar, tool'lardan keyingi holat.
- **Tool'lar (TZ 7.4)** — `ai/tools.py`: `search_product`, `get_product_details`, `check_stock`, `recommend`, `calc_delivery`, `get_payment_card`, `search_knowledge_base` (RAG), `handoff_to_operator`. CRM ma'lumotiga grounding.
- **LLM abstraksiyasi** — `ai/llm/`: `base` (Protocol) · `openai_provider` (real, TZ 3) · `fake_provider` (test) · `factory`. Provayder swappable.
- **Agent orkestratsiya** — `ai/agent.py`: gating (ai_enabled/paused/closed) → memory → prompt → tool-calling sikli → guardrail → `ai_send` → state. Worker `inbox.process_incoming` shu agentni ishga tushiradi (`task_session`).
- **CRM API** — `ai/router.py`: KB CRUD, `GET /ai/prompt`, `POST /ai/conversations/{id}/respond` (qo'lda trigger).
- **Tayyor mezoni:** AI mustaqil tovar tavsiya qiladi, guardrail buziladigan javob chiqmaydi. ✔ (FakeProvider bilan uchdan-uchiga smoke)

**Faza 3 qarorlari:**
- **LLM = OpenAI** (TZ 3-bo'lim). `LLM_PROVIDER` (openai|fake|none); kalit yo'q → AI **jim** turadi (fabrikatsiya yo'q). Provayder abstraksiyasi tufayli Claude/lokal model qo'shsa bo'ladi (TZ 19 PII eslatmasi).
- **Test LLM'siz:** guardrail/tool/memory/RAG/state to'liq testlanadi; agent sikli `FakeProvider` (skriptli) bilan.
- **Embedding _generatsiyasi_ hali yo'q** — KB/media embedding ustunlari bor, hnsw indeks bor; embedding to'ldirish OpenAI embeddings bilan keyin (RAG hozir tsvector orqali).
- **Buyurtma/lokatsiya/to'lov tool'lari (create_order/request_location/submit_payment)** ataylab REGISTRATSIYA QILINMADI — orders/delivery/payments modullari Faza 4/5. Agent hozir tavsiya + savol bosqichigacha olib boradi.
- AI javobi `ai_paused_until` QO'YMAYDI (faqat operator qo'yadi).

### ✅ Faza 4 — Buyurtma + lokatsiya + yetkazish (TUGADI)
- **`orders` moduli:** `order`, `order_item`, `order_status_history` + `OrdersService` (create_order + **reservation** + status tarixi + cancel).
- **`delivery` moduli:** `delivery`, `checkout_token` + `DeliveryService` (checkout link, lokatsiya resolve, zona fixed narx).
- Migratsiya `0005_orders`: 5 jadval + FK/unique/indekslar.
- **Reservation (TZ 10):** `create_order`→`reserved_qty++` (zaxira band); `cancel`→`reserved_qty--` (bo'shaydi); `stock_qty--` — to'lov approved (Faza 5). `stocked` variant uchun availability tekshiruvi.
- **Buyurtma invariantlari (TZ 18):** `order_item.ring_size` (o'lcham order'da), `bonus_snapshot` (global bonus nusxasi), `unit_price` (yaratish vaqtidagi fixed narx). `order_no` unikal generatsiya.
- **Checkout token (TZ 11/15):** `POST /delivery/orders/{id}/checkout-link` → bir martalik link; public `GET/POST /checkout/{token}`. Token **hash saqlanadi**, muddatli (24h), **one-time/replay himoya**, expiry tekshiruvi.
- **Yetkazish (TZ 11):** zona fixed narx (Toshkent 50k→provider yandex / viloyat 30k→bts). Lokatsiya resolve → `order.delivery_fee`+`grand_total`, status `pending→waiting_payment`. Yandex API yo'q.
- **AI tool'lari ulandi:** `create_order`, `request_location` (Faza 3'da kechiktirilgan) → agent buyurtma yaratadi va checkout link yuboradi; state machine `ordering`/`awaiting_location`.
- **Tayyor mezoni:** AI buyurtma yaratadi, lokatsiya token bilan bog'lanadi, narx to'g'ri. ✔ (jonli Postgres smoke: reservation, checkout create/resolve/replay/expiry, cancel, AI buyurtma)

**Faza 4 qarorlari:**
- Enumlar `VARCHAR` (Pydantic validatsiya). Narxlar `Numeric(12,2)`.
- Checkout link bazaviy URL — `PUBLIC_BASE_URL` (env). Muddat — `CHECKOUT_TOKEN_EXPIRY_HOURS` (24).
- `stock_qty--` (haqiqiy kamaytirish) **Faza 5**'da (to'lov approved). Hozir faqat `reserved_qty`.
- Buyurtma tasdiqlash (`confirmed`) va to'lov oqimi — **Faza 5**.

### ✅ Faza 5 — To'lov (TUGADI)
- **`payments` moduli:** `payment` (order_id UNIQUE), `payment_card` + migratsiya `0006_payments`.
- **Prepaid oqim (TZ 12):** `submit_payment` → payment `pending` + order `payment_review` + owner botiga xabar → `approve`/`reject`.
- **Approve:** idempotent (bir marta), `reviewed_by`/`reviewed_at`, **`stock_qty--`/`reserved_qty--`** (TZ 10), order → `confirmed` (operatorga tushadi), mijozga xabar.
- **Reject:** `reject_reason_required` (settings) tekshiruvi, **`reserved_qty--`** (band bo'shaydi, TZ 10), mijozga xabar.
- **Owner bot oqimi (TZ 12):** `NotificationService` chekni owner/manager Telegram chatiga **✅/❌ inline tugmalar** bilan yuboradi; `callback_query` webhook'da qayta ishlanadi (`handle_payment_callback`).
- **Object storage (MinIO):** `ReceiptStorage` (boto3) — `POST /payments/receipts` chekni yuklaydi.
- **Payment card:** CRUD + `is_primary` (bitta). AI `get_payment_card` endi jadvaldan o'qiydi; `submit_payment` AI tool ulandi (state → `payment_review`).
- **Tayyor mezoni:** chek owner botiga boradi, tasdiq → buyurtma operatorga tushadi. ✔ (jonli Postgres smoke: submit/approve idempotent+stock/reject/callback/AI)

**Faza 5 qarorlari:**
- **Kartalar `payment_card` jadvalida** (TZ 6.2) — settings `payment_cards`/`primary_card` eskirgan (legacy).
- Owner tasdiqlovchi: HTTP `POST /payments/{id}/approve` → `reviewed_by=joriy user` (aniq, TZ-mos). Bot tugmasi → `settings.payment_reviewer_user_id` (bo'lsa), aks holda NULL.
- Idempotentlik: approved payment qayta approve — no-op (stock ikki marta kamaymaydi).
- Chek yuklash uchun MinIO servisi kerak (compose'da bor); dev testda receipt_url string bilan tekshirildi.
- Telegram tugma bilan reject — `reason=None` (agar `reject_reason_required=true` bo'lsa CRM'dan rad etiladi).

### ✅ Faza 6 — RBAC to'liq + Analytics + Notifications + Audit (TUGADI)
- **RBAC to'liq (TZ 13):** `identity/rbac_service.py` + `/rbac/*` — permission ro'yxati (matritsa), **custom rol** CRUD, **rol permission checkbox** (`PUT /rbac/roles/{id}/permissions`), user (xodim) CRUD + rol tayinlash. System rol o'chirilmaydi. O'zgarishда **Redis permission cache invalidatsiya** (ta'sirlangan userlar).
- **Audit (TZ 6.2/15):** `audit_log` modeli + migratsiya `0007` + `AuditService` (atomik: chaqiruvchi tranzaksiyasi bilan). Ulangan: `payment.approve/reject`, `role.create/delete/set_permissions`, `user.create/update/set_roles/delete`. `GET /audit` (`audit:view`).
- **Analytics (TZ 1):** `AnalyticsService` + `GET /analytics/dashboard` — KPI: sales_conversion, lead_conversion, ai_handled_share, ai_created_orders, revenue, orders_by_status, payment approval_rate.
- **Notifications:** `notification` jadvali + owner alert qaydi (sent/failed/skipped), `GET /notifications`.
- **`order.created_by_ai`** (migratsiya 0007) — AI `create_order` tool True qo'yadi (KPI 3).
- **Tayyor mezoni:** rol/permission matritsa + custom rol, dashboard KPI'lar, audit log. ✔ (jonli Postgres+Redis smoke)

**Faza 6 qarorlari:**
- Permission cache: rol/permission yoki user rol o'zgarganда tegishli userlar cache'i Redis'dan tozalanadi (TZ 13).
- Audit atomik (alohida commit emas) — harakat bilan bir tranzaksiyaga tushadi.
- KPI ba'zilari taxminiy (lead_conversion = buyurtma bergan mijoz/suhbat); `ai_handled_share` = operator xabari yo'q + AI xabari bor suhbatlar.
- Row-level scoping (`user_role.scope`) sxemasi bor; qo'llash (filtrlash) — kelajak/Faza 7.

### ✅ Faza 7 — Hardening (TUGADI)
- **Rate limit (TZ 15):** `core/rate_limit.py` — Redis fixed-window, IP bo'yicha. Login (brute-force) va webhook endpointlariga ulangan. `429` javob.
- **Token revocation (TZ 15):** JWT'ga `jti`, `core/token_blacklist.py` (Redis TTL). `POST /auth/logout` refresh'ni bekor qiladi; `refresh` blacklist'ni tekshiradi.
- **Prompt injection (TZ 15):** `guardrail.py` — `detect_injection` (uz/en/ru naqshlar) + `sanitize_user_input` rol-spoofing (`system:`) zararsizlantirish.
- **Proaktiv qayta jalb (TZ 17):** `inbox/reengagement.py` — IG 24h oynasi ichida jim qolgan (oxirgi xabar mijozdan) suhbatlarga nudge. Celery `inbox.proactive_reengage` + **beat schedule** + compose `beat` servisi. Spamга qarshi: jalbdan keyin oxirgi xabar chiquvchi bo'ladi.
- **Monitoring/logging (TZ 16):** `core/logging_config.py` (structlog JSON) + request middleware (request_id, latency) + **`GET /health/ready`** (DB+Redis).
- **DevOps (TZ 16):** `scripts/backup.sh` (pg_dump + MinIO mirror), `.github/workflows/ci.yml` (compile+migrate+seed+import), nginx xavfsizlik headerlari + rate limit + TLS blok (izohда).
- **API hujjatlari himoyasi:** `/docs`, `/redoc`, `/openapi.json` — **HTTP Basic** (`DOCS_USERNAME`/`DOCS_PASSWORD`, constant-time solishtiruv, `DOCS_AUTH_ENABLED`). FastAPI standart `docs_url/redoc_url/openapi_url` o'chirilgan va himoyalangan holda qayta ochilgan. `/health*` ochiq (probe).
- **Tayyor mezoni:** rate limit, prompt injection himoya, proaktiv jalb, monitoring/backup, deploy. ✔ (jonli Postgres+Redis smoke)

**Faza 7 qarorlari:**
- Schema o'zgarmadi (yangi migratsiya yo'q) — jti/blacklist Redis'da, reengagement mavjud maydonlardan.
- Access token qisqa muddatli (30 min) — logout refresh'ni bekor qiladi; access tabiiy tugaydi.
- Row-level scoping (`user_role.scope`) — sxema tayyor, to'liq filtrlash qo'llash keyingi iteratsiyaga (mexanizm bor).
- Beat davri/inactivity/window — env orqali (`REENGAGEMENT_*`); default o'chirilgan (`REENGAGEMENT_ENABLED=false`).

---

## 🎉 BARCHA FAZALAR (0–7) TUGADI
Tizim to'liq: identity/RBAC · catalog · inbox (IG/TG) · AI agent (guardrail/tools/RAG) · orders · delivery · payments · analytics · audit · notifications · hardening. Har faza jonli Postgres(+Redis) da smoke test bilan tasdiqlangan. Migratsiyalar: `0001`–`0007`.

---

## Ishga tushirish (qisqa)
```bash
cp .env.example .env
docker compose up --build
# login: admin@almazsilver.uz / admin123 (.env: SEED_ADMIN_*)
```
Batafsil: [`README.md`](./README.md).
