# Almaz — AI Seller + CRM (Zargarlik)

Instagram va Telegram orqali kelgan mijozlarni **AI sotuvchi** yordamida avtonom
sotuvga olib boradigan CRM platforma. Brend: **almazsilver** (Kumush 925 + rodiy, serkon toshi).

> Arxitektura: **Modulli Monolit** (FastAPI + PostgreSQL/pgvector + Redis + RabbitMQ/Celery + MinIO).
> To'liq spetsifikatsiya: [`TZ_zargarlik_ai_seller_crm.md`](./TZ_zargarlik_ai_seller_crm.md).

---

## 📦 Joriy holat: BARCHA FAZALAR (0–7) TUGADI ✅

- **Faza 0:** modulli FastAPI skeleti, Docker Compose, JWT+refresh auth, RBAC skeleton, `setting` jadvali.
- **Faza 1:** `product/variant/product_media/category` + admin CRUD, 3 qatlamli qidiruv
  (SKU → IG shortcode → tsvector GIN), pgvector semantik qidiruv (hnsw), IG shortcode mapping.
- **Faza 2:** `customer/conversation/message` + IG/TG webhook (imzo tekshiruvi), inbox CRM API
  (list/thread/send/transfer/assign), 15-daqiqa AI pauzasi, Celery inbound (AI ilmog'i).
- **Faza 3:** AI agent — guardrail (serkon/Kumush 925/fixed narx), tool-calling (search/recommend/
  details/stock/delivery/card/RAG/handoff), prompt/memory/state machine, `knowledge_base` (RAG).
- **Faza 4:** `order/order_item/delivery/checkout_token` + reservation, checkout token sahifa
  (one-time, hash, expiry), zona fixed narx; AI `create_order`/`request_location` tool'lari.
- **Faza 5:** `payment/payment_card` prepaid oqim — submit→owner botiga (✅/❌ tugma)→approve
  (idempotent, stock--)/reject, chek MinIO'ga, AI `submit_payment`/`get_payment_card` tool'lari.
- **Faza 6:** RBAC to'liq (custom rol, permission matritsa, cache invalidatsiya), `audit_log`
  (approve/rol/user), KPI dashboard, `notification` qaydi.
- **Faza 7:** hardening — rate limit (Redis), token revocation (logout), prompt injection himoya,
  proaktiv qayta jalb (IG 24h, Celery beat), structured logging + `/health/ready`, backup + CI/CD.

Keyingi fazalar uchun: [`CLAUDE.md`](./CLAUDE.md) (stack, konvensiyalar, faza holati).

---

## 🚀 Ishga tushirish

### Talablar
- Docker + Docker Compose

### Qadamlar

```bash
# 1) Muhit faylini tayyorlang (dev default'lar bilan ishlaydi)
cp .env.example .env

# 2) Barcha servislarni ko'taring (build + migratsiya + seed avtomatik)
docker compose up --build
```

`api` servisi ishga tushishда avtomatik: `alembic upgrade head` → `python -m app.seed` → `uvicorn`.

### Servislar

| Servis | Manzil | Izoh |
|---|---|---|
| API (FastAPI) | http://localhost:8000 | to'g'ridan-to'g'ri |
| API (Nginx orqali) | http://localhost:80 | reverse proxy |
| Swagger UI | http://localhost:8000/docs | interaktiv API — **login/parol bilan** 🔒 |
| ReDoc | http://localhost:8000/redoc | hujjatlar — **login/parol bilan** 🔒 |
| RabbitMQ UI | http://localhost:15672 | guest / guest |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| PostgreSQL | localhost:5432 | almaz / almaz |

---

## 📖 API hujjatlari (himoyalangan)

`/docs`, `/redoc` va `/openapi.json` **HTTP Basic login/parol** bilan yopilgan (`.env` dan):

| Sozlama | Default |
|---|---|
| `DOCS_USERNAME` | `admin` |
| `DOCS_PASSWORD` | `almaz-docs` |
| `DOCS_AUTH_ENABLED` | `true` (o'chirish uchun `false`) |

Brauzerда http://localhost:8000/docs ochilganda login oynasi chiqadi. CLI bilan:

```bash
curl -s -u admin:almaz-docs http://localhost:8000/openapi.json | head
```
> ⚠️ Prod'da `DOCS_PASSWORD` ni albatta almashtiring. `/health` va `/health/ready` ochiq qoladi (probe uchun).

---

## 🔐 Tekshirish (login + RBAC)

Boshlang'ich Super Admin (`.env` dan): **admin@almazsilver.uz** / **admin123**

```bash
# 1) Health
curl http://localhost:8000/health

# 2) Login → access + refresh token
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@almazsilver.uz","password":"admin123"}'

# 3) Joriy foydalanuvchi + permission'lar (RBAC ishlashini isbotlaydi)
TOKEN="<access_token>"
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"

# 4) Token yangilash
curl -s -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'

# 5) Sozlamalar (settings:view permission talab qiladi)
curl -s http://localhost:8000/settings -H "Authorization: Bearer $TOKEN"
```

### Katalog (Faza 1)

```bash
# Mahsulot qo'shish (default variant + IG media avtomatik)
curl -s -X POST http://localhost:8000/catalog/products \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name":"Kumush uzuk serkon toshli",
    "price":450000, "compare_at_price":900000,
    "ai_keywords":["uzuk","kumush","ayollar"],
    "media":[{"shortcode_or_url":"https://www.instagram.com/p/CabcXYZ_1/"}]
  }'

# Qidiruv — matn (tsvector)
curl -s "http://localhost:8000/catalog/search?q=serkon+uzuk" -H "Authorization: Bearer $TOKEN"
# Qidiruv — IG link (shortcode)
curl -s "http://localhost:8000/catalog/search?q=https://www.instagram.com/p/CabcXYZ_1/" -H "Authorization: Bearer $TOKEN"
# Qidiruv — SKU aniq
curl -s "http://localhost:8000/catalog/search?sku=<SKU>" -H "Authorization: Bearer $TOKEN"

# Zaxira o'rnatish
curl -s -X POST http://localhost:8000/catalog/variants/<variant_id>/stock \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"stock_qty":5}'
```

### Inbox / integratsiyalar (Faza 2)

```bash
# Telegram webhook simulatsiyasi (secret .env: TELEGRAM_WEBHOOK_SECRET)
curl -s -X POST http://localhost:8000/webhooks/telegram \
  -H "X-Telegram-Bot-Api-Secret-Token: dev-telegram-secret" -H "Content-Type: application/json" \
  -d '{"message":{"message_id":1,"from":{"id":555,"username":"ali","first_name":"Ali"},"chat":{"id":555},"text":"Kumush uzuk bormi?"}}'

# Suhbatlar ro'yxati (conversations:view)
curl -s http://localhost:8000/inbox/conversations -H "Authorization: Bearer $TOKEN"
# Xabarlar
curl -s http://localhost:8000/inbox/conversations/<id>/messages -H "Authorization: Bearer $TOKEN"
# Operator javobi (AI 15 daqiqa pauza qiladi)
curl -s -X POST http://localhost:8000/inbox/conversations/<id>/messages \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"Ha, bor. Narxi 450000 so'\''m."}'
```
> **Real IG/TG ulash:** `.env`da `TELEGRAM_BOT_TOKEN`, `INSTAGRAM_APP_SECRET`,
> `INSTAGRAM_PAGE_ACCESS_TOKEN`, `INSTAGRAM_VERIFY_TOKEN` to'ldiriladi; Telegram
> `setWebhook` va Meta webhook `.../webhooks/instagram` ga yo'naltiriladi.

### AI Agent (Faza 3)

```bash
# Bilim bazasi (RAG) — ko'rish
curl -s http://localhost:8000/ai/knowledge -H "Authorization: Bearer $TOKEN"
# Joriy system prompt + versiya
curl -s http://localhost:8000/ai/prompt -H "Authorization: Bearer $TOKEN"
# Agentni qo'lda ishga tushirish (LLM kaliti kerak; ai:override_ai)
curl -s -X POST http://localhost:8000/ai/conversations/<id>/respond -H "Authorization: Bearer $TOKEN"
```
> **AI'ni yoqish:** `.env`da `LLM_PROVIDER=openai` + `OPENAI_API_KEY=...`. Kalit bo'lmasa
> AI **jim** turadi (hech narsa fabrikatsiya qilmaydi). Kelgan xabar Celery `inbox.process_incoming`
> orqali agentni ishga tushiradi. Guardrail har javobni tekshiradi (serkon/Kumush 925/fixed narx).

### Buyurtma + yetkazish (Faza 4)

```bash
# Buyurtma yaratish (zaxira band qilinadi)
curl -s -X POST http://localhost:8000/orders -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_id":"<id>","items":[{"variant_id":"<vid>","quantity":1,"ring_size":"18"}]}'

# Checkout (lokatsiya) linki generatsiya — mijozga yuboriladi
curl -s -X POST http://localhost:8000/delivery/orders/<order_id>/checkout-link -H "Authorization: Bearer $TOKEN"

# Mijoz sahifasi (OCHIQ, token bilan): kontekst + lokatsiya yuborish
curl -s http://localhost:8000/checkout/<token>
curl -s -X POST http://localhost:8000/checkout/<token> -H "Content-Type: application/json" \
  -d '{"zone":"tashkent","address_text":"Chilonzor 5","lat":41.31,"lng":69.24}'
```
> Zona narxi qat'iy: Toshkent 50 000 / viloyat 30 000 (`.env`/Settings). Token bir martalik,
> hash saqlanadi, 24 soat amal qiladi (replay/expiry himoya).

### To'lov (Faza 5)

```bash
# Asosiy karta qo'shish (settings:manage_settings)
curl -s -X POST http://localhost:8000/payments/cards -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"holder_name":"ALMAZ SILVER","card_number_masked":"8600****1234","is_primary":true}'

# Chek yuklash (object storage) → url qaytadi
curl -s -X POST http://localhost:8000/payments/receipts -H "Authorization: Bearer $TOKEN" -F "file=@chek.jpg"

# To'lovni yuborish (order payment_review'ga o'tadi, owner botiga xabar ketadi)
curl -s -X POST http://localhost:8000/payments/submit -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"order_id":"<id>","receipt_url":"<url>","payer_name":"Aziz Azizov"}'

# Tasdiqlash → stock_qty--, buyurtma confirmed (payments:approve)
curl -s -X POST http://localhost:8000/payments/<payment_id>/approve -H "Authorization: Bearer $TOKEN"
```
> **Owner bot tasdig'i:** `.env`/Settings'da `payment_review_telegram_chat_id` (owner chat) va
> `payment_reviewer_user_id` (javobgar CRM user) sozlanadi. Chek ✅/❌ tugmalari bilan boradi;
> tugma bosilsa `callback_query` webhook orqali tasdiq/rad bo'ladi.

### RBAC / Analytics / Audit (Faza 6)

```bash
# Permission matritsa (barcha kodlar)
curl -s http://localhost:8000/rbac/permissions -H "Authorization: Bearer $TOKEN"
# Custom rol yaratish + permission tayinlash (checkbox)
curl -s -X POST http://localhost:8000/rbac/roles -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name":"Custom Sales"}'
curl -s -X PUT http://localhost:8000/rbac/roles/<role_id>/permissions -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"codes":["orders:view","products:view"]}'
# Xodim yaratish + rol
curl -s -X POST http://localhost:8000/rbac/users -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Sardor","email":"sardor@almaz.uz","password":"secret6","role_ids":["<role_id>"]}'

# KPI dashboard
curl -s http://localhost:8000/analytics/dashboard -H "Authorization: Bearer $TOKEN"
# Audit log
curl -s http://localhost:8000/audit -H "Authorization: Bearer $TOKEN"
```

### Hardening (Faza 7)

```bash
# Readiness (DB + Redis)
curl -s http://localhost:8000/health/ready
# Logout (refresh token bekor qilinadi)
curl -s -X POST http://localhost:8000/auth/logout -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh>"}'
```
> **Rate limit** login/webhook'да yoqilgan (`RATE_LIMIT_*`). **Proaktiv qayta jalb** — `beat`
> servisi + `REENGAGEMENT_ENABLED=true` bilan. **Backup:** `scripts/backup.sh` (cron).
> **CI:** `.github/workflows/ci.yml`. **TLS/nginx:** `nginx/nginx.conf`da sertifikat bilan yoqiladi.

> To'liq endpointlar ro'yxati: http://localhost:8000/docs

Super Admin barcha permission'larga ega, shuning uchun `/settings` ochiladi.
Permissionsiz token bilan `403 Ruxsat yo'q` qaytadi.

---

## 🧱 Loyiha tuzilishi

```
app/
├── main.py            # FastAPI fabrikasi (routerlarni yig'adi)
├── celery_app.py      # Celery worker entrypoint
├── seed.py            # Boshlang'ich ma'lumot (idempotent)
├── core/              # umumiy infratuzilma: config, db, security, deps, redis
└── modules/           # bounded contexts (TZ 4-bo'lim)
    ├── identity/      # ✅ auth + RBAC  (router/service/repository/models)
    ├── settings/      # ✅ key-value sozlamalar
    └── ...            # inbox, catalog, orders, ... (bo'sh skelet — keyingi fazalar)
migrations/            # Alembic (0001_phase0_foundation)
docker-compose.yml     # api, worker, postgres, redis, rabbitmq, minio, nginx
```

Har modul qatlamlari: **router → service → repository → models** (TZ 4-bo'lim).

---

## 🛠 Foydali buyruqlar

```bash
# Loglar
docker compose logs -f api
docker compose logs -f worker

# Seed'ni qayta ishga tushirish (idempotent)
docker compose exec api python -m app.seed

# Yangi migratsiya generatsiya (model o'zgargach)
docker compose exec api alembic revision --autogenerate -m "izoh"
docker compose exec api alembic upgrade head

# To'xtatish / tozalash (volume bilan)
docker compose down
docker compose down -v
```
# Almaz.Silver
