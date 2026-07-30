# Frontend — Kategoriyaga o'lcham (razmer) bog'lash

> Kim uchun: frontend dasturchisi.
> Migratsiya `0023`. Jonli Postgres test: brief/order — o'tgan.
> Bazaviy URL (prod): `https://almaz.api.cognilabs.org` · Auth: `Authorization: Bearer <access_token>`

## 1. G'oya (nima va nega)

O'lcham **mahsulotga emas, KATEGORIYAga** bog'lanadi (TZ invariant: o'lcham variant emas, `order_item`da).

- Kategoriyada `requires_ring_size` — *"bu kategoriyada o'lcham talab qilinadimi?"* (masalan **Uzuklar** = `true`,
  braslet/sepochka/zirak = `false`).
- `requires_ring_size=true` bo'lsa — `available_sizes` bilan **mavjud o'lchamlar ro'yxati** beriladi
  (masalan `["16","16.5","17","17.5","18"]`).
- `available_sizes` **ixtiyoriy**: bo'sh/`null` — istalgan o'lcham qabul qilinadi (cheklovsiz, eski xulq).

Bir marta kategoriyaga qo'yiladi — o'sha kategoriyadagi HAMMA mahsulot (uzuk) shu o'lchamlarni oladi.

---

## 2. Ma'lumot modeli

| Maydon | Tur | Izoh |
|---|---|---|
| `requires_ring_size` | bool | Kategoriyada o'lcham kerakmi |
| `available_sizes` | string[] \| null | Mavjud o'lchamlar. `null`/bo'sh — cheklovsiz. Faqat `requires_ring_size=true` da mazmunli |

O'lchamlar — **string** (`"16.5"` kabi kasrlar uchun). Tartib siz bergancha saqlanadi.

---

## 3. API — Kategoriya CRUD (o'lcham maydoni qo'shildi)

Ruxsatlar: ko'rish `products:view`, yaratish `products:create`, tahrirlash `products:update`.

### 3.1. Yaratish — `POST /catalog/categories`  (`products:create`)
```json
{
  "name_uz": "Uzuklar",
  "name_ru": "Кольца",
  "requires_ring_size": true,
  "available_sizes": ["16", "16.5", "17", "17.5", "18"]
}
```
Javob `200` — `CategoryOut` (§4).

### 3.2. Tahrirlash — `PATCH /catalog/categories/{category_id}`  (`products:update`)
Faqat o'zgargan maydonlarni yuboring (partial). O'lchamlarni yangilash:
```json
{ "available_sizes": ["15", "16", "17", "18", "19", "20"] }
```
O'lchamlarni **tozalash** (cheklovsiz qilish):
```json
{ "available_sizes": null }
```
Javob `200` — yangilangan `CategoryOut`.

### 3.3. Ro'yxat / bitta
- `GET /catalog/categories` → `Page<CategoryOut>` (`products:view`).
- `GET /catalog/categories/{category_id}` → `CategoryOut`.

---

## 4. `CategoryOut` (javob obyekti)
```json
{
  "id": "uuid",
  "name_uz": "Uzuklar",
  "name_ru": "Кольца",
  "slug": "uzuklar",
  "parent_id": null,
  "requires_ring_size": true,
  "available_sizes": ["16", "16.5", "17", "17.5", "18"]
}
```
`available_sizes` — `string[]` yoki `null`.

---

## 5. Mahsulot javobida ham ko'rinadi — `ProductOut`

Buyurtma/mahsulot formasi alohida kategoriya so'rovsiz o'lchamlarni bilishi uchun `ProductOut` ham
qaytaradi (kategoriyadan olinadi):
```json
{
  "id": "uuid",
  "name_uz": "Minimalist uzuk 'Sokin'",
  "requires_ring_size": true,
  "available_sizes": ["16", "16.5", "17", "17.5", "18"],
  "...": "..."
}
```
- `requires_ring_size=false` (braslet va h.k.) → `available_sizes: null` (o'lcham so'ralmaydi).
- `requires_ring_size=true` lekin kategoriyada ro'yxat yo'q → `available_sizes: null` (istalgan o'lcham).

`GET /catalog/products` / `GET /catalog/products/{id}` — shu maydon bilan qaytaradi.

---

## 6. Ketma-ketliklar (flow)

### A) Admin — kategoriyaga o'lcham qo'yadi
```
1. Admin "Kategoriyalar" sahifasida kategoriya ochadi (GET /catalog/categories/{id}).
2. "O'lcham talab qilinadimi?" toggle = HA  -> requires_ring_size=true.
   -> shundagina "Mavjud o'lchamlar" maydoni KO'RINADI (chips input).
3. O'lchamlarni kiritadi: 16, 16.5, 17, 17.5, 18.
4. Saqlash -> PATCH /catalog/categories/{id} { requires_ring_size: true, available_sizes: [...] }.
5. Javob 200 -> forma yangilanadi. Endi shu kategoriyadagi hamma uzuk shu o'lchamlarni oladi.
```
> Toggle "YO'Q" bo'lsa (`requires_ring_size=false`) — o'lcham maydonini yashiring; `available_sizes`
> yubormang yoki `null` yuboring.

### B) Mijoz — buyurtma (AI + backend avtomatik)
```
1. Mijoz uzuk tanlaydi. AI mahsulot brief'ida available_sizes ni oladi.
2. AI o'lchamni so'raydi va FAQAT ro'yxatdagilarni taklif qiladi:
   "Mavjud o'lchamlar: 16, 16.5, 17, 17.5, 18 — qaysi biri?"
3. Mijoz ro'yxatdagi o'lchamni tanlaydi -> buyurtma yaratiladi (order_item.ring_size).
4. Agar (biror yo'l bilan) ro'yxatdan tashqari o'lcham kelsa -> backend 400 qaytaradi:
   { "detail": "Bu kategoriyada mavjud o'lchamlar: 16, 16.5, 17, 17.5, 18. '20' o'lchami mavjud emas." }
```
> Frontend buyurtma/checkout formasida ham `ProductOut.available_sizes` bilan **dropdown/chips**
> ko'rsatsa — mijoz noto'g'ri o'lcham kirita olmaydi (400 ga tushmaydi).

---

## 7. Buyurtma validatsiyasi (backend qoidasi)

`POST /orders` (yoki AI `create_order`) — har item uchun:
- `available_sizes` bo'sh/`null` → istalgan `ring_size` qabul qilinadi.
- `available_sizes` to'ldirilgan → `ring_size` ro'yxatда bo'lishi SHART, aks holda `400`:
  ```json
  { "detail": "Bu kategoriyada mavjud o'lchamlar: 16, 16.5, 17, 17.5, 18. '20' o'lchami mavjud emas." }
  ```
- `requires_ring_size=false` (universal) → `ring_size` umuman tekshirilmaydi.

---

## 8. Xatolar

| Holat | HTTP | detail |
|---|---|---|
| Ro'yxatdan tashqari o'lcham (buyurtma) | 400 | "Bu kategoriyada mavjud o'lchamlar: … '{size}' o'lchami mavjud emas." |
| Kategoriya topilmadi | 404 | "Mahsulot/Kategoriya topilmadi" |
| Ruxsat yo'q | 403 | products:create/update kerak |
| Token yo'q/eskirgan | 401 | — |

---

## 9. Frontend UX tavsiyalari

- **Kategoriya formasi:** `requires_ring_size` toggle → HA bo'lsa "Mavjud o'lchamlar" chips-input ko'rsating
  (yangi teg qo'shish/o'chirish). Bo'sh qoldirsa "cheklovsiz" degan izoh chiqaring.
- **O'lcham qiymati:** matn (string) sifatida saqlang — `"16.5"`, `"17"` (kasr uchun). Xohlasangiz
  frontendда validatsiya (raqam/kasr) qo'ying, lekin backend string qabul qiladi.
- **Buyurtma formasi:** mahsulot uzuk bo'lsa (`requires_ring_size=true`) va `available_sizes` bo'lsa —
  o'lchamni **dropdown/chips** bilan tanlating (erkin matn EMAS) → 400 xatosini oldini olasiz.
- **Bo'sh ro'yxat:** `available_sizes` `null`/bo'sh bo'lsa — o'lcham maydonini erkin matn qoldiring
  (istalgan o'lcham).
