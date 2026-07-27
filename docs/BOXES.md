# Box (rangli quti) — kategoriya bo'yicha qadoq qutilari

> Migratsiya `0016_boxes`. Jonli Postgres smoke: **12/12**.

Mahsulot buyurtmasiga qo'shiladigan **rangli quti** xizmati. Foydalanuvchi qarorlari asosida:

| Qaror | Tanlov |
|---|---|
| Struktura | Har **kategoriya** o'z rang ro'yxatiga ega (M2M emas). Ranglar **dynamic** — cheklovsiz qo'shish/o'chirish. |
| Rang & count | Har rang **alohida yozuv**: o'z narxi + o'z zaxirasi (Variant kabi). |
| Narx | Har **rangda** narx: `0 = tekin`, `>0 = pulli`. Ba'zi rang tekin, ba'zisi pulli bo'lishi mumkin. |
| Buyurtmaga | Har **mahsulot (order_item)** uchun ixtiyoriy 1 box — o'lcham/gravyurka kabi, narx snapshot. |
| Boshqaruv | **«category bo'limi»**da (kategoriyaga scoped endpointlar). |

## 1. Ma'lumotlar sxemasi

**`box`** — kategoriyaning bitta rangli qutisi:
`category_id`(FK→category, CASCADE) · `name_uz`/`name_ru`(rang nomi) · `color_hex`(UI swatch) ·
`price`(Numeric, 0=tekin) · `stock_qty`/`reserved_qty`(zaxira, TZ 10) · `is_active`/`sort_order` ·
`deleted_at`(soft delete — tarixiy buyurtmalar butun qoladi). Property: `available`, `is_free`.

**`order_item`** ga qo'shildi (engraving andozasi — snapshot):
`box_id`(FK→box, ON DELETE SET NULL) · `box_price`(buyurtma vaqtidagi bir dona narx) · `box_label`("Uzuklar — Qizil").

## 2. Admin API (`/catalog/*`, RBAC: `products:*`) — «category bo'limi»
```
GET    /catalog/categories/{id}/boxes        # kategoriya ranglari (pagination, only_active)
POST   /catalog/categories/{id}/boxes        # rang qo'shish {name_uz,color_hex,price,stock_qty,...}
GET    /catalog/boxes/{box_id}
PATCH  /catalog/boxes/{box_id}               # nom/rang/narx/faollik/tartib
DELETE /catalog/boxes/{box_id}               # soft delete
POST   /catalog/boxes/{box_id}/stock         # {stock_qty} yoki {delta} — count boshqaruvi
```
> Misol: «Uzuklar» kategoriyasida 6 rang; 3 tasi `stock_qty>0` (qolgan) — AI faqat shularni taklif qiladi.

## 3. Buyurtma + zaxira (TZ 10 — variant bilan bir xil)
- **Narx:** `items_total += (unit_price + engraving_price + box_price) × quantity` (har donaga box).
- **Reservation:** `create_order` → `box.reserved_qty++` (mavjudlik + kategoriya mosligi tekshiriladi);
  `cancel` → `--`; **to'lov approved** → `stock_qty--`/`reserved_qty--`; **reject** → `reserved_qty--`.
- **Validatsiya:** `boxes_enabled=false` → xato; box boshqa kategoriyaga tegishli → xato; zaxira yetarsiz → xato.
- **Snapshot:** box narxi/rangi keyin o'zgarsa yoki o'chsa, eski buyurtmalar o'zgarmaydi.

## 4. Settings
`boxes_enabled` (global on/off). Narx/rang/zaxira — Settings'da emas, har kategoriyada (box jadvali).

## 5. AI (guardrail-mos)
- `get_product_details` va yangi `list_boxes` tool natijasida `boxes` (rang + narx + zaxira) qaytadi —
  faqat **zaxirada bor** ranglar.
- System prompt: `boxes` bo'sh bo'lmasa rang taklif qilsin, narxni **FAQAT** box `price` dan aytsin
  (`0` → tekin), ro'yxatda yo'q rangni **o'ylab topmasin** (guardrail mosligi).
- `create_order` da har item uchun `box_id` (ixtiyoriy).

## 6. Worker/metadata
Box `catalog/models.py` da — `migrations/env.py` va `app/core/models_registry.py` allaqachon catalog'ni
import qiladi, ya'ni worker FK'ni (`order_item.box_id → box`) muammosiz ko'radi.

## Sozlash (deploy)
```bash
git pull && docker compose up -d --build   # 0016 migratsiya avtomatik
# kategoriyaga ranglar qo'shish:
POST /catalog/categories/{id}/boxes {"name_uz":"Qizil","color_hex":"#E53935","price":0,"stock_qty":10}
POST /catalog/categories/{id}/boxes {"name_uz":"Ko'k","price":5000,"stock_qty":5}
```

## Tekshirildi: 12/12 (jonli Postgres)
box create(free/paid) · list_active_boxes · items_total(+box) · box_price snapshot · box_label ·
reservation(reserved++) · kategoriya mos emas→xato · zaxira yetarsiz→xato · cancel→release ·
stock adjust(delta) · tekin box(price 0) · soft delete→ro'yxatda yo'q.
