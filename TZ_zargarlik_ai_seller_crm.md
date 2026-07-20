# Zargarlik AI Seller + CRM — Texnik Topshiriq (TZ)

> **Bu hujjat nima?** Loyihani **noldan** qurish uchun to'liq spetsifikatsiya. Claude Code (yoki boshqa AI agent) shu faylni o'qib, tizimni bosqichma-bosqich implement qilishi mumkin. Har qaror uchun sabab ("nima uchun") berilgan. Kod identifikatorlari inglizcha, izohlar o'zbekcha.
>
> **Prinsip:** modulli, kengaytiriladigan (scalable), xavfsiz (secure), yuqori yuklamaga (high-load) mos. Hech bir modul tashlab ketilmasin.

---

## 1. LOYIHA MAQSADI VA KPI

**Maqsad:** Instagram va Telegram orqali kelgan mijozlarni **AI sotuvchi (agent)** yordamida to'liq avtonom sotuvga olib boradigan CRM platforma. AI professional sotuvchi rolini bajaradi; operator faqat tasdiqlangan buyurtmani jismonan jo'natadi.

**AI ning KPI'lari:**
1. Sales Conversion — suhbatdan buyurtmaga aylanish.
2. Lead Conversion — yozgan mijozning malakali lead'ga aylanishi.
3. Buyurtma yaratish — AI o'zi yaratgan buyurtmalar soni.
4. Operator yukini kamaytirish — AI mustaqil hal qilgan suhbatlar ulushi.

---

## 2. BIZNES KONTEKSTI

- **Biznes:** bitta zargarlik do'koni (single-tenant), butun O'zbekiston bo'ylab. Brend: almazsilver.
- **Material:** **faqat Kumush 925 proba + rodiy qoplama** (oltin yo'q).
- **Tosh:** **serkon (tsirkon / CZ)**. Mijozga aynan "serkon toshi" deb aytiladi.
- **Assortiment:** hozir ~12 model. Turlari:
  - `uzuk` (~97%, erkak uzuklari ham),
  - `braslet`,
  - `sepochka` (zanjir),
  - `komplekt` (set).
- **Narx:** har model uchun **qat'iy (fixed)** narx (gramm kursi bilan bog'liq emas). Doimiy "chegirma" taktikasi: yuqori eski narx (`compare_at_price`) + arzon yangi narx (`price`).
- **Bonuslar:** upakovka + brend paket — barcha buyurtmalarga bir xil (global sozlama).
- **Kafolat:** bor (sifat kafolati). *(Aniq shartlar — Settings, keyin egadan.)*

---

## 3. TEXNOLOGIYALAR

| Qatlam | Texnologiya | Nima uchun |
|---|---|---|
| Backend | **FastAPI (Python 3.12+)** | Async — webhook + LLM oqimi uchun ideal |
| DB | **PostgreSQL 16 + pgvector** | Relational + semantik qidiruv/rasm fallback |
| Cache / rate limit | **Redis** | Cache, permission cache, rate limit, session |
| Queue | **RabbitMQ + Celery** | Og'ir ishlar (LLM, xabar yuborish, notification) asinxron |
| AI | **GPT (OpenAI) function-calling** | Sotuvchi agent; RAG bilan katalogga grounding |
| Instagram | **Meta Graph API** | Rasmiy DM integratsiyasi |
| Telegram | **Telegram Bot API** | Rasmiy bot |
| Object storage | **S3-mos (MinIO / cloud)** | Mahsulot/chek/voice fayllar |
| Frontend (CRM UI) | **React** | Operator/admin paneli |
| Infra | **Docker + Compose, Nginx** | Bir xil muhit, reverse proxy |
| Auth | **JWT + refresh** | Kirish nazorati |

**Arxitektura uslubi:** Modulli Monolit (Modular Monolith). *Nima uchun:* hajm (~1000 chat/kun) monolit uchun qulay; mikroservis ortiqcha murakkablik. Modulli tuzilish keyinchalik modulni alohida service'ga ajratishga tayyor.

---

## 4. UMUMIY ARXITEKTURA

**Modullar (bounded contexts):** `identity` (auth, RBAC) · `inbox` (chat) · `catalog` · `inventory` · `orders` · `delivery` · `payments` · `ai` (agent + knowledge base) · `settings` · `analytics` · `audit` · `notifications`.

**Qatlamlar:** API (FastAPI routers) → Service layer (biznes logikasi) → Repository layer (DB kirish) → Unit of Work (tranzaksiya). Dependency Injection orqali bog'lanadi. CQRS shart emas (hajm buni talab qilmaydi; oddiy service/repository yetarli).

**Komponentlar:**
- **Webhook Ingestor** — IG/TG'dan xabar qabul qiladi, imzoni (signature) tekshiradi, tez `200 OK` qaytaradi, ishni queue'ga qo'yadi.
- **Queue + Celery Workers** — LLM chaqiruvi, IG/TG'ga javob, notification, proaktiv qayta jalb.
- **AI Agent Core** — prompt manager, memory, conversation state machine, tool calling.
- **CRM API** — barcha biznes logikasi + web UI uchun endpointlar.
- **PostgreSQL (+pgvector)**, **Redis**, **Object Storage**.

---

## 5. RUNTIME KETMA-KETLIK (end-to-end)

1. **Xabar keladi.** Mijoz IG DM / TG bot orqali yozadi → webhook FastAPI'ga tushadi. Ingestor imzoni tekshiradi.
2. **Saqlash + navbat.** Xabar `message` jadvaliga yoziladi, queue'ga qo'yiladi, `200 OK` qaytadi. Hech bir xabar yo'qolmaydi.
3. **AI ishga tushadi.** Celery worker: conversation state + memory yuklaydi. Agar `conversation.ai_paused_until > now()` (operator aralashgan) → AI jim.
4. **AI suhbatni yuritadi.** GPT mijoz ehtiyojini aniqlaydi, kerak bo'lsa tool chaqiradi.
5. **Tovar aniqlash.** IG link kelsa → `shortcode` ajratiladi → `product_media` dan aniq mahsulot. Topilmasa → pgvector/tavsif bo'yicha eng mos taklif. Link yo'q, "shu kerak" desa → AI "Instagram post linkini yuboring" deydi.
6. **Buyurtma yaratish.** AI o'lchamni so'raydi (sovg'a bo'lsa — o'rta o'lcham yoki ip bilan o'lchash), `order` + `order_item` (+ `ring_size`) yaratadi, zaxira band qilinadi (`reserved_qty++`).
7. **Lokatsiya + yetkazish.** AI bir martalik token bilan checkout link yuboradi → mijoz xarita pin/manzil tanlaydi → buyurtmaga bog'lanadi. Zona fixed narxi qo'shiladi (Toshkent 50k / viloyat 30k).
8. **To'lov.** AI asosiy kartani beradi → mijoz chek rasmi + ism-familiya yuboradi → bot orqali owner/manager'ga tasdiqlash/rad tugmalari bilan boradi.
9. **Tasdiq.** Owner tasdiqlasa → `stock_qty--`, buyurtma `confirmed → preparing`, operatorga tushadi. Rad etsa → (sabab optional) mijozga xabar.
10. **Jo'natish.** Operator chiqaradi (Toshkent kuryer/Yandex, viloyat BTS — qo'lda), status `shipping → delivered → completed`.

Butun jarayonda **guardrail** har javobni tekshiradi, barcha muhim harakatlar **audit_log**'ga yoziladi.

---

## 6. MA'LUMOTLAR BAZASI

### 6.1. Umumiy tamoyillar
- UUID PK (`gen_random_uuid()`), `created_at`/`updated_at` hamma jadvalda (`timestamptz`).
- **Soft delete** (`deleted_at`) faqat: `product`, `variant`, `customer`, `user`.
- **Reservation:** `available = stock_qty − reserved_qty`.
- **Audit:** universal `audit_log` + `order_status_history`.

### 6.2. Asosiy jadvallar

**catalog**
- `category(id, name, slug, parent_id?)`
- `product(id, category_id, name, gender[erkak|ayol|uniseks], material, stone, price, compare_at_price, status[draft|active|archived], description, ai_keywords jsonb, search_vector tsvector, deleted_at?)`
- `variant(id, product_id, sku UNIQUE, barcode? UNIQUE, fulfillment_type[stocked|made_to_order|unique] default stocked, stock_qty, reserved_qty, is_active, deleted_at?)`
- `product_media(id, product_id, channel[instagram|telegram], external_media_id, shortcode UNIQUE, permalink, image_url, embedding vector(1536)?)`

> **Muhim qaror 1 — o'lcham variant EMAS.** Uzuk o'lchami buyurtmada belgilanadi (`order_item.ring_size`), hamma o'lcham bir xil narx, kerak bo'lsa 1 kunда moslanadi. Bu bir modeldan 50–500 SKU chiqishini yopadi. `variant` hozirgi katalogда asosan **1:1** (har product'ga bitta default variant); qatlam komplekt/kelajak uchun saqlanadi.

> **Muhim qaror 2 — zaxira `variant` ichida.** Bitta do'kon, ~12 model, bitta ombor — alohida `inventory_item/level` mashinasi ortiqcha. Ko'p ombor kerak bo'lsa keyin qo'shiladi.

**inbox**
- `customer(id, channel[instagram|telegram], external_id, username, full_name?, phone?, language, source, deleted_at?)` — UNIQUE `(channel, external_id)`
- `conversation(id, customer_id, channel, ai_state, status, assigned_operator_id?, ai_paused_until?, unread_count, last_message?, last_activity_at)`
- `message(id, conversation_id, direction[incoming|outgoing], sender_type[customer|ai|operator|system], sender_user_id?, content, attachments jsonb, tool_call jsonb, delivery_status[pending|sent|delivered|read|failed], is_read, edited_at?, created_at)`

> **15-daqiqalik handoff:** operator yozsa `ai_paused_until = now() + settings.ai_pause_minutes`. AI faqat `now() > ai_paused_until` bo'lganда javob beradi.

**orders**
- `order(id, order_no UNIQUE, customer_id, assigned_operator_id?, status, items_total, delivery_fee, grand_total, created_at)`
- `order_item(id, order_id, variant_id, quantity, unit_price, ring_size?, bonus_snapshot jsonb)`
- `order_status_history(id, order_id, from_status, to_status, changed_by, created_at)`

**delivery**
- `delivery(id, order_id UNIQUE, zone[tashkent|region], provider[yandex|bts], fee, address_text?, lat?, lng?, status[pending|awaiting_address|ready|dispatched|delivered])`
- `checkout_token(id, order_id, token_hash UNIQUE, expires_at, used, created_at)`

**payments**
- `payment(id, order_id UNIQUE, card_id?, status[pending|approved|rejected], receipt_url, payer_name, reject_reason?, reviewed_by?, reviewed_at?, created_at)`
- `payment_card(id, holder_name, card_number_masked, is_primary, is_active)`

**identity / RBAC** (7-bo'lim, 13-bo'lim)
- `user(id, full_name, email UNIQUE, password_hash, is_active, deleted_at?)`
- `role(id, name, is_system)`, `permission(id, code)`, `role_permission(role_id, permission_id)`, `user_role(user_id, role_id, scope jsonb?)`

**settings / audit / ai**
- `setting(key UNIQUE, value jsonb)`
- `audit_log(id, actor_id?, action, entity_type, entity_id, before jsonb?, after jsonb?, ip?, created_at)`
- `knowledge_base(id, type[faq|policy|delivery|payment|company|guarantee|instruction], title, content, embedding vector(1536)?)`

### 6.3. Indekslar
- `product.search_vector` → **GIN** (o'zbekcha to'liq matn: nom + teg + ai_keywords + sinonim).
- `product_media.embedding` → **pgvector (hnsw)**.
- `message(conversation_id, created_at)`, `conversation(status, last_activity_at)`, `order(status, created_at)`, `payment(status)`.

---

## 7. AI AGENT

### 7.1. Conversation state machine
`greeting → browsing → recommending → ordering → awaiting_location → awaiting_payment → payment_review → handed_off → closed`

Har xabarда: worker joriy `ai_state` + memory (oldingi N xabar + mijoz profili) ni yuklaydi, GPT'ga uzatadi, javob va yangi state'ni oladi.

### 7.2. Prompt Manager
- Versiyalangan promptlar (`settings.prompt_version`). System prompt: rol (professional zargarlik sotuvchisi), til qoidasi (mijoz tilida, "siz"lab), va **guardrail** (15-bo'lim).
- Sozlanadigan: `ai_temperature`, `llm_model` (Settings orqali).

### 7.3. Memory
- Qisqa muddat: joriy conversation'ning oxirgi xabarlari.
- Uzoq muddat: mijoz profili (ismi, tili, oldingi buyurtmalar) — takroriy mijozdan ma'lumot qayta so'ralmaydi.

### 7.4. Tool'lar (function-calling)
| Tool | Vazifa |
|---|---|
| `search_product(query? | shortcode? | image?)` | Katalogdan tovar topish (matn/IG link/rasm) |
| `get_product_details(product_id)` | To'liq ma'lumot: narx, material="Kumush 925+rodiy", tosh="serkon" |
| `check_stock(variant_id)` | `available = stock_qty − reserved_qty` |
| `recommend(context)` | Upsell / cross-sell tavsiya |
| `calc_delivery(zone)` | Zona bo'yicha fixed fee (Settings'dan) |
| `create_order(customer_id, items[{variant_id, quantity, ring_size?}])` | Buyurtma yaratish + reservation |
| `request_location(order_id)` | Bir martalik checkout link generatsiya |
| `get_payment_card()` | Asosiy (primary) karta |
| `submit_payment(order_id, receipt_url, payer_name)` | Chekni owner/manager botiga uzatish |
| `handoff_to_operator(conversation_id, reason)` | Operatorga o'tkazish (kerak bo'lganda) |

### 7.5. Tovar aniqlash (Instagram Product Detection)
- **Asosiy (deterministik):** IG URL → `shortcode` → `product_media.shortcode` (UNIQUE) → aniq mahsulot. 1 soniyada.
- **Fallback:** mijoz rasm tashlasa yoki noaniq yozsa → `pgvector` embedding bo'yicha eng mos mahsulot(lar).
- **Link yo'q, "shu kerak" desa** → AI "Iltimos, o'sha post linkini yuboring" deydi.
- **Topilmasa** → operatorga eskalatsiya **qilmaydi** (operator javob vaqti noaniq), balki eng yaqin variantlarni taklif qiladi.

### 7.6. RAG (Knowledge Base)
AI barcha javoblarni CRM ma'lumotidan oladi: `product`, `knowledge_base` (FAQ, policy, delivery, payment, company, guarantee, instruction). Semantik qidiruv (pgvector) + tsvector. AI o'zidan narx/ma'lumot **o'ylab topmaydi**.

---

## 8. KATALOG MODULI

- **Universal "mahsulot qo'shish" oynasi**, lekin ko'rinadigan maydonlar `category`/optionга qarab o'zi kengayadi/qisqaradi (uzukда `ring_size` order'da; braslet/sepochka/komplekt — o'lchamsiz). Alohida kod shart emas.
- **Bonuslar global** (Settings'da `bonus_items`), har tovarga alohida yozilmaydi.
- **Qidiruv 3 qatlam:** (1) SKU/barcode aniq mos; (2) IG shortcode lookup; (3) tsvector (nom/teg/ai_keywords/sinonim) + pgvector (rasm/semantik).
- Har mahsulotда bir nechta rasm, video; IG (kerak bo'lsa TG) permalink saqlanadi.

---

## 9. INBOX / CHAT

- IG + TG xabarlar bitta inbox'da, kanal bo'yicha ajratiladi (`conversation.channel`).
- Har xabarда kim yozgani ko'rinadi (`sender_type`: customer/ai/operator/system).
- Attachment: rasm/video/voice (voice → transkripsiya, keyin matn). `delivery_status` kuzatiladi.
- Operator "transfer chat" qila oladi (permission bilan). Operator yozgach 15-daqiqa AI pauzasi.

---

## 10. BUYURTMA OQIMI

**Statuslar:** `draft → pending → waiting_payment → payment_review → confirmed → preparing → packed → shipping → delivered → completed` (+ `cancelled`, `refunded`, `returned`).

**Reservation transitions:**
- `create_order` → `reserved_qty++` (zaxira band).
- to'lov `approved` → `stock_qty--`, `reserved_qty--`.
- `cancelled` / to'lov `rejected` → `reserved_qty--` (band bo'shaydi).

Har status o'zgarishi `order_status_history`'ga yoziladi.

---

## 11. YETKAZISH

- **Mijoz to'laydi.** To'lovdan oldin zona bo'yicha **fixed** narx qo'shiladi:
  - Toshkent → **50 000** so'm (`delivery_fee_tashkent`),
  - Viloyat (BTS) → **30 000** so'm (`delivery_fee_region`).
  - Ikkalasi ham Settings'dan edit qilinadi.
- **Yandex API integratsiyasi YO'Q** (fixed narx yetarli). *Sabab:* integratsiya murakkabligi hozir shart emas; kerak bo'lsa keyin `provider=yandex` uchun API ulanadi (kengaytirish tayyor).
- **BTS** — operator qo'lda chiqaradi.

**Instagram lokatsiya muammosi — yechim (checkout token):**
1. AI buyurtma bosqichida mijozdan lokatsiya kerak bo'lsa → CRM `customer` mavjudligini tekshiradi/yaratadi.
2. **Bir martalik token** generatsiya qilinadi (`checkout_token`: `token_hash` saqlanadi, `expires_at` ~24h, `used=false`).
3. Mijozga checkout sahifa linki yuboriladi.
4. Mijoz sahifani ochadi → **Toshkent:** xarita pin; **viloyat:** BTS struktura manzil (viloyat/tuman/...).
5. Tasdiqlaganда: token tekshiriladi (muddati o'tmagan, ishlatilmagan) → lokatsiya buyurtmaga bog'lanadi → `used=true`.

**Xavfsizlik:** token ochiq saqlanmaydi (hash), `expires`, **one-time use**, replay himoya, HTTPS (transit shifrlash).

---

## 12. TO'LOV

- **Faqat prepaid** (COD yo'q). Settings'dan `payment_required` bilan yoqiladi/o'chiriladi.
- **Kartalar:** bir nechta bo'lishi mumkin (`payment_card`), bittasi **asosiy** (`is_primary`). AI asosiy kartani beradi.

**Oqim:**
1. AI mijozga asosiy karta raqamini beradi.
2. Mijoz **chek rasmi** + **karta egasi ism-familiyasi** yuboradi.
3. `payment` (status=`pending`) yaratiladi; chek object storage'ga.
4. **Bot** buyurtma ma'lumoti + summalar bilan owner/manager'ga (tanlangan user) **tasdiqlash / rad etish** tugmalari bilan uzatadi.
5. **Tasdiq** → status `approved`, `reviewed_by`/`reviewed_at` yoziladi, zaxira `stock_qty--`, buyurtma operatorga tushadi.
6. **Rad** → status `rejected`; agar `reject_reason_required=true` bo'lsa sabab so'raladi (aks holda so'ralmaydi); mijozga xabar.

**Muhim:**
- Tasdiqlagan xodim "to'landi" qaroriga **to'liq javobgar** (`reviewed_by`).
- **Idempotentlik:** bitta `payment` bir marta approve bo'ladi (takroriy bosishда holat o'zgarmaydi).

---

## 13. RBAC & PERMISSIONS

**Prinsip:** sodda ko'rinish, cheklanmagan imkoniyat. System rollar + admin yaratadigan **custom rollar** + har permission checkbox orqali.

**System rollar:** Super Admin, Owner, General Manager, Sales Manager, Operator, Support, Warehouse, Courier Manager, Finance, Marketing, Content Manager, AI Manager, Analyst, Auditor, Guest.

**Permission kodlari (action × resource):**
- Actionlar: `view, create, update, delete, export, approve, assign, transfer_chat, refund, override_ai, edit_prompt, manage_roles, view_reports, view_cost, view_profit, manage_delivery, manage_products, manage_employees, manage_integrations, manage_settings, system_access`.
- Resurslar: `customers, orders, products, inventory, payments, delivery, conversations, ai, employees, roles, settings, analytics, audit`.
- Kod formati: `resource:action` (masalan `orders:approve`, `ai:edit_prompt`).

**Namuna matritsa (asosiy):**

| Permission | Super Admin | Owner | General Mgr | Sales Mgr | Operator | Finance | Warehouse | AI Manager | Auditor | Guest |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| system_access | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| manage_roles | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| manage_settings | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| manage_products | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| orders:view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ | ➖ |
| orders:approve (payment) | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ |
| orders:refund | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ | ➖ |
| transfer_chat | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ |
| override_ai | ✅ | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ |
| ai:edit_prompt | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ |
| view_cost / view_profit | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | ➖ | ➖ | ✅ | ➖ |
| manage_delivery | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | ✅ | ➖ | ➖ | ➖ |
| manage_integrations | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| audit:view | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ | ✅ | ➖ |

> (Bu boshlang'ich default; admin har katakni checkbox bilan o'zgartira oladi va yangi rol yaratadi.)

**Row-level scoping (ABAC element):** `user_role.scope` (jsonb) orqali — masalan operator faqat o'ziga assign qilingan suhbatlar/buyurtmalarni ko'radi; region bo'yicha cheklov. **Permission cache** (Redis) — har so'rovda DB'ga bormaslik uchun.

---

## 14. SETTINGS (barcha biznes logikasi shu yerdan)

`payment_required` · `reject_reason_required` · `delivery_enabled` · `ai_enabled` · `instagram_enabled` · `telegram_enabled` · `working_hours` · `auto_reply` · `operator_timeout` · `ai_pause_minutes` (default 15) · `ai_temperature` · `llm_model` · `prompt_version` · `delivery_fee_tashkent` (50000) · `delivery_fee_region` (30000) · `yandex_enabled` · `bts_enabled` · `bonus_items` (upakovka, brend paket) · `payment_cards` + `primary_card`.

> Ish vaqtidan tashqari: AI **o'zi sotishni davom ettiradi** (to'liq avtonom); operator asosan buyurtmani chiqaradi.

---

## 15. XAVFSIZLIK

- **Auth:** JWT + refresh token; parol hash (argon2/bcrypt).
- **RBAC + permission cache** (13-bo'lim).
- **Webhook security:** IG/TG imzo (signature) tekshiruvi; faqat haqiqiy so'rovlar.
- **Rate limit** (Redis) — API va webhook.
- **Encryption:** transit HTTPS; secrets `.env`/secret manager'da (repo'ga tushmaydi).
- **Checkout token:** hash, expire, one-time, replay himoya.
- **PII himoya:** mijoz shaxsiy ma'lumotlari cheklangan kirish bilan.
- **LLM Guardrails (KRITIK — biznes qoidasi):**
  - Tosh doim **"serkon toshi"** — AI hech qachon "olmos / diamond / brilliant / tabiiy tosh" demaydi.
  - Material doim **"Kumush 925 + rodiy qoplama"**.
  - Narx doim katalogdagi **fixed narx** — AI narx o'ylab topmaydi/savdolashmaydi.
  - Chiqish (output) validatsiya qatlami har javobni shu qoidalarga tekshiradi, keyin yuboradi.
- **Prompt Injection himoya:** mijoz matni system ko'rsatmalarini bekor qila olmaydi (input sanitizatsiya + ajratilgan rol).
- **Audit:** har muhim CRUD/approve/refund/override/edit_prompt `audit_log`'ga.

---

## 16. DEVOPS

- **Docker + Docker Compose** servislar: `api` (FastAPI), `worker` (Celery), `postgres` (+pgvector), `redis`, `rabbitmq`, `nginx`, `minio` (object storage).
- **Nginx** — reverse proxy, TLS, static.
- **CI/CD** — test + build + deploy pipeline.
- **Monitoring/Logging** — structured logging; xatolar kuzatuvi.
- **Backup** — PostgreSQL muntazam backup; object storage backup.

---

## 17. QURISH TARTIBI (fazalar + "tayyor" mezoni)

- **Faza 0 — Poydevor.** Repo, Docker Compose (postgres+pgvector, redis, rabbitmq, minio), FastAPI skelet, JWT auth, RBAC skeleton, `setting` jadvali.
  - *Tayyor:* login ishlaydi, permission tekshiruvi bor, servislar ko'tariladi.
- **Faza 1 — Katalog + zaxira.** `product/variant/product_media`, admin CRUD, qidiruv (GIN + pgvector), IG shortcode mapping.
  - *Tayyor:* mahsulot qo'shiladi/topiladi (SKU, matn, IG link, rasm bo'yicha).
- **Faza 2 — Inbox + integratsiyalar.** IG/TG webhook + imzo, `message/conversation`, chat UI, xabar yuborish.
  - *Tayyor:* IG/TG'dan xabar kelib inbox'da ko'rinadi, javob yuboriladi.
- **Faza 3 — AI Agent (yadro).** Prompt/memory/state machine, tool calling (search/recommend/order/delivery), **guardrail**.
  - *Tayyor:* AI mustaqil tovar tavsiya qiladi, guardrail buziladigan javob chiqmaydi.
- **Faza 4 — Buyurtma + lokatsiya + yetkazish.** Order lifecycle + reservation, checkout token sahifa, delivery fee.
  - *Tayyor:* AI buyurtma yaratadi, lokatsiya token bilan bog'lanadi, narx to'g'ri.
- **Faza 5 — To'lov.** Prepaid bot oqimi, tasdiq/rad (+optional sabab), object storage, idempotentlik.
  - *Tayyor:* chek owner botiga boradi, tasdiq → buyurtma operatorga tushadi.
- **Faza 6 — RBAC to'liq + Analytics + Notifications + Audit.**
  - *Tayyor:* rol/permission matritsa + custom rol, dashboard KPI'lar, audit log.
- **Faza 7 — Hardening.** Rate limit, prompt injection himoya, proaktiv qayta jalb (IG 24-soat oynasi), monitoring/backup, deploy.

> Har faza oldingisiga tayanadi. 0→1→2→3 bo'lgach tizim "jonli" (AI qidirib javob beradi); qolganlari sotuvni yakunlaydi va mustahkamlaydi.

---

## 18. MUHIM QARORLAR VA INVARIANTLAR (recap)

1. **O'lcham variant emas** → `order_item.ring_size`; hamma o'lcham bir narx; 1 kunда moslanadi.
2. **Zaxira `variant` ichida** (`stock_qty`/`reserved_qty`); alohida ombor jadvalisiz (kengaytirish tayyor).
3. **Bonuslar global** (Settings), har tovarga emas.
4. **Guardrail:** serkon toshi / Kumush 925+rodiy / fixed narx — AI hech qachon buzmaydi.
5. **Prepaid majburiy** (Settings orqali); to'lov tasdiqlanmaguncha jo'natilmaydi; tasdiqlagan xodim javobgar.
6. **Yetkazish zona bo'yicha fixed** (Toshkent 50k / viloyat 30k), Yandex API yo'q.
7. **15-daqiqalik AI pauzasi** operator aralashganда; AI to'liq avtonom sotuvchi, operator faqat chiqaradi.
8. **Til:** mijoz tilida, "siz"lab hurmat bilan.

---

## 19. KEYIN ANIQLANADIGAN (kichik, blocker emas)

1. **Qaytarish/almashtirish** aniq shartlari (kafolat "bor", lekin muddat/qamrov aytilmagan) — Settings'da parametrlaydi, aniq shart egadan.
2. **PII / localization** — mijoz shaxsiy ma'lumotlari GPT (chet el) API'siga chiqishi huquqiy jihatdan tekshirilsin; kerak bo'lsa PII'ni LLM'ga yubormaslik (masking) yoki mahalliy model varianti ko'rib chiqilsin.

---

*Ushbu TZ 22 modul (Instagram/Telegram integratsiya, AI agent, katalog, buyurtma, yetkazish, to'lov, RBAC, settings, xavfsizlik, DevOps va h.k.) ni qamraydi. Claude Code shu tartibда (17-bo'lim) implement qilishi mumkin.*
