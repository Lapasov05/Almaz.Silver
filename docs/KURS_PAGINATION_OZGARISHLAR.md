# Kurs + kartalar CRUD + pagination/filter — o'zgarishlar (migratsiya `0010_kurs`)

> Talab: kartalarга to'liq CRUD · kurs (gramm narxi) bir nechta, to'liq CRUD, kategoriyaga ulangan ·
> chatlarда filterlar · **hamma GET'larга pagination + iloji boricha ko'p filter**.
> **Holat: bajarildi va tekshirildi — 37/37 test o'tdi.**

---

## 1. Pagination — hamma ro'yxat (GET) endpointlarда

Javob shakli **hamma list'да bir xil** (`app/core/pagination.py`):
```json
{ "items": [ ... ], "total": 137, "limit": 50, "offset": 0 }
```
So'rov: `?limit=50&offset=0` (limit 1–200, reference/dropdown lar uchun 1–1000).

**Qamralган endpointlar (16 ta):**
`/catalog/products` · `/catalog/categories` · `/catalog/genders` · `/catalog/materials` ·
`/catalog/stones` · `/catalog/kurs` · `/orders` · `/payments` · `/payments/cards` ·
`/inbox/conversations` · `/inbox/.../messages` · `/ai/knowledge` · `/audit` ·
`/notifications` · `/rbac/users` · `/rbac/roles` · `/rbac/permissions`.

> `/settings` (konfiguratsiya, ~27 kalit) va qidiruv (`/catalog/search`) pagination'siz qoldi
> (ular butunicha yuklanadi / o'ziga xos javob shakli).

## 2. Kurs (gramm narxi) — to'liq CRUD, kategoriyaga ulangan

Yangi `kurs` jadvali: `category_id` (FK), `value` (1 gramm narxi), `is_active`, `note`.
O'tgan safar qo'shilgan `category.gram_price` **kursga ko'chirildi** (migratsiya avtomatik) va o'chirildi.

```
GET    /catalog/kurs?category_id=<id>&is_active=true     (pagination)
GET    /catalog/kurs/{id}
POST   /catalog/kurs      {category_id, value, is_active, note}
PATCH  /catalog/kurs/{id} {value?, is_active?, note?}
DELETE /catalog/kurs/{id}
```

- **Bir kategoriyada bir nechta kurs** bo'lishi mumkin. Kalkulyator **eng oxirgi aktiv** kursni oladi
  (`is_active=true`, `created_at` bo'yicha eng yangisi).
- `GET /catalog/categories` javobida `active_gram_price` — o'sha kategoriyaning aktiv kursi.
- `GET /catalog/price-calc?category_id=..&weight_grams=..` — narxni hisoblab beradi (aktiv kursdan).
- Mahsulot yaratishда narx berilmasa: `price = weight_grams × (kategoriya aktiv kursi)`.

## 3. To'lov kartalari — to'liq CRUD

Ilgari bor edi: list, create, update. **Qo'shildi:** GET by id, DELETE + `is_active` filtri.
```
GET    /payments/cards?is_active=true       (pagination)
GET    /payments/cards/{id}
POST   /payments/cards                       (settings:manage_settings)
PATCH  /payments/cards/{id}                  (settings:manage_settings)
DELETE /payments/cards/{id}                  (settings:manage_settings)
```

## 4. Chat (inbox) filterlari

`GET /inbox/conversations`:
| Filter | Ma'nosi |
|---|---|
| `status` | open / closed |
| `channel` | telegram / instagram |
| `ai_state` | greeting / recommending / ordering / ... |
| `assigned_operator_id` | operatorga tayinlangan |
| `unread_only=true` | faqat o'qilmagan (unread_count>0) |
| `q` | mijoz ismi / username / external_id bo'yicha |

`GET /inbox/conversations/{id}/messages`: `direction` (incoming/outgoing), `sender_type` (customer/ai/operator/system) + pagination.

## 5. Boshqa endpointlardagi filterlar

| Endpoint | Filterlar (query) |
|---|---|
| `/catalog/products` | status, category_id, gender_id, material_id, stone_id, engraving_available, in_stock, min_price, max_price, q (uz/ru) |
| `/catalog/categories` | parent_id, q |
| `/catalog/{genders,materials,stones}` | only_active, q |
| `/orders` | status, customer_id, assigned_operator_id, created_by_ai, order_no, date_from, date_to |
| `/payments` | status, order_id, reviewed_by, date_from, date_to |
| `/ai/knowledge` | type, q (title/content) |
| `/audit` | action, entity_type, entity_id, actor_id, date_from, date_to |
| `/notifications` | type, status, channel |
| `/rbac/users` | q (ism/email), is_active, role_id |
| `/rbac/roles` | q, is_system |
| `/rbac/permissions` | q |

---

## ⚠️ Frontend uchun BREAKING o'zgarishlar

1. **Hamma list endpoint endi massiv emas, `{items,total,limit,offset}` obyekti qaytaradi.**
   Front `res.data` o'rniga `res.data.items` ishlatsin; `total` sahifalash uchun.
2. Kategoriyada `gram_price` maydoni **yo'q** — o'rniga `active_gram_price` (o'qish uchun),
   narx boshqaruvi endi `/catalog/kurs` orqali.

## O'zgargan fayllar

`core/pagination.py` (yangi) · catalog {models, schemas, repository, service, router} ·
`migrations/versions/0010_kurs.py` · payments {repository, service, router} ·
orders {repository, router} · inbox {repository, router} · ai {repository, service, router} ·
audit {service, router} · notifications/router · identity {repository, rbac_service, admin_router} ·
demo_seed.py

## Tekshirildi

| Test | Natija |
|---|:--:|
| Migratsiya 0001→0010 (gram_price → kurs ko'chirish) | ✅ 10/10 |
| Pagination + CRUD + filter smoke (ASGI) | ✅ **37/37** |

Tasdiqlar: 16 list endpoint envelope qaytaradi · limit/offset+total · kurs CRUD + kalkulyator
eng oxirgi aktiv kursdan (2×170000=340000) · kartalar CRUD · mahsulot/chat/buyurtma/audit/user filterlari.
demo_seed (7 buyurtma + to'lov oqimi) yangi sxemada muvaffaqiyatli o'tdi.

## Deploy

```bash
git pull
docker compose up -d --build     # 0010 migratsiya avtomatik (gram_price -> kurs)
```
