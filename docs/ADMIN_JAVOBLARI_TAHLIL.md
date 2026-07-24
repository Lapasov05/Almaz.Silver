# Almaz.Silver — admin javoblari vs. loyiha (moslik tahlili)

> Maqsad: adminlar bergan javoblarни tizimда bor-yo'qligini tekshirish. **Kod o'zgartirilmadi** — faqat tahlil.
> Qisqa xulosa: loyiha aynan shu biznes TZ'sidan qurilgani uchun **javoblarning ~95% i to'g'ridan-to'g'ri qamrab olingan**. 2 ta kichik bo'shliq bor (strukturaviy maydon emas, bilim bazasi/sozlama orqali yopiladi).

Belgilar: ✅ to'liq bor · ⚠️ qisman (matn/KB orqali, strukturaviy maydon yo'q) · ❌ yo'q

---

## 1. Mahsulotlar

| # | Admin javobi | Tizimда | Qayerda | Holat |
|---|---|---|---|:--:|
| 1.1 | Uzuk (97%), braslet, sepochka, komplekt; erkak uzuklari ham | Turlar `category` jadvali orqali; erkak uzuk `product.gender = erkak` (enum: erkak/ayol/uniseks) | `catalog/models.py` → `Category`, `Product.gender` | ✅ |
| 1.2 | ~12 xil assortiment | Model sonida qat'iy chegarov yo'q; TZ "~12 model" bilan mos | — | ✅ |
| 1.3 | Faqat Kumush 925 + rodiy qoplama, oltin yo'q | `product.material` default "Kumush 925 + rodiy"; guardrail "oltin/gold" → "Kumush 925 + rodiy" | `catalog/models.py`, `ai/guardrail.py` (`_RULES`) | ✅ |
| 1.4 | Toshni "serkon toshi" deб aytamiz | Guardrail: "olmos/diamond/brilliant/tabiiy tosh" → **"serkon toshi"** ga majburiy almashtiradi; KB "Material va tosh"; system prompt | `ai/guardrail.py`, `ai/knowledge_defaults.py`, `ai/prompts.py` | ✅ |

**Izoh 1.1:** Adminlar sirg'a/kulon (marjon) aytmadi — demak assortiment: uzuk / braslet / sepochka / komplekt. Hammasi `category` orqali kiritiladi (universal "mahsulot qo'shish" oynasi). **Komplekt** — bitta `product` sifatida (bir narx). Komponentlarni alohida omborда sanash hozir yo'q — TZ bo'yicha kutilgan (variant qatlami kelajak uchun saqlangan).

**Izoh 1.4 (KRITIK, mos):** Admin aynan "serkon toshi" dedi — guardrail xuddi shu so'zни majburlaydi va AI hech qachon "olmos/tabiiy tosh" demaydi. Bu 100% to'g'ri sozlangan.

---

## 2. O'lcham

| # | Admin javobi | Tizimда | Qayerda | Holat |
|---|---|---|---|:--:|
| 2.1 | Asosan 16-17-18; 15/19/20 ni katta/kichik qilib beramiz | `order_item.ring_size` — **erkin matn** (String), istalgan o'lcham qabul qilinadi | `orders/models.py` → `OrderItem.ring_size` | ✅ |
| 2.2 | O'lcham buyurtma paytida aniqlanadi | **Muhim qaror 1:** o'lcham variant EMAS, `order_item.ring_size` da | `orders/models.py`, `orders/service.py` | ✅ |
| 2.3 | Sovg'a bo'lsa o'rta (hodovoy) razmer taklif; yoki ip/qog'oz bilan o'lchash | System prompt: "sovg'a bo'lsa — o'rta o'lcham yoki ip bilan o'lchashni taklif qiling"; KB "O'lcham" yozuvi | `ai/prompts.py`, `ai/knowledge_defaults.py` | ✅ |
| 2.4 | Hamma o'lcham bir xil narx | Invariant: o'lcham variant emas → **hamma o'lchamда bir narx** (`product.price`) | `orders/service.py` (narx variantдан emas, product'dan) | ✅ |

**Izoh 2.1:** 15/19/20 "katta/kichik qilib berish" — `ring_size` erkin matn bo'lgani uchun texnik jihatдан to'liq ishlaydi (bir narx, 1 kunда moslanadi). Alohida "nostandart o'lcham" bayrog'i yo'q, lekin biznes mantig'iga (bir narx) mos, shuning uchun kerak emas.

---

## 3. Ombor va tayyorlik

| # | Admin javobi | Tizimда | Qayerda | Holat |
|---|---|---|---|:--:|
| 3.1 | Omborда tayyor turadi | `variant.fulfillment_type = stocked` (default) + `stock_qty`/`reserved_qty` | `catalog/models.py` → `Variant` | ✅ |
| 3.2 | 1 kunда tayyor | **Strukturaviy "tayyorlik muddati" maydoni yo'q.** KB "O'lcham"да "kerak bo'lsa 1 kunда moslanadi" bor | `ai/knowledge_defaults.py` | ⚠️ |
| 3.3 | Yagona nusxa emas — har doim tegi bo'ladi | `stock_qty` to'ldirib turiladi; `fulfillment_type = unique` ishlatilmaydi | `catalog/models.py` | ✅ |

**Bo'shliq 3.2:** "1 kunда tayyor/yetkazamiz" umumiy ma'lumoti hozir faqat o'lcham konteкstida (KB matni). Strukturaviy maydon shart emas — **bilim bazasiga (KB) bitta yozuv qo'shish** yoki settings'ga `preparation_days` kalitини qo'shish kifoya. Bu **kod o'zgarishisiz** hal bo'ladi (KB CRUD yoki `PUT /settings/...` orqali).

---

## 4. Narx va chegirma

| # | Admin javobi | Tizimда | Qayerda | Holat |
|---|---|---|---|:--:|
| 4.1 | Narx qat'iy belgilangan summa; grammga bog'liq emas | `product.price` (Numeric, fixed); guardrail: AI narх o'ylab topmaydi/savdolashmaydi | `catalog/models.py`, `ai/prompts.py` | ✅ |
| 4.2 | Har doim chegirma: qimmat eski narx / arzon yangi narx | `product.compare_at_price` (eski narx) + `product.price` (yangi narx) — aynan shu taktika | `catalog/models.py` → `compare_at_price` | ✅ |

**Izoh 4.2:** Bu 1:1 mos — `compare_at_price` maydoni aynan "eski qimmat narx"ni ko'rsatish uchun qo'shilган.

---

## Umumiy natija

| Bo'lim | Savollar | ✅ To'liq | ⚠️ Qisman | ❌ Yo'q |
|---|:--:|:--:|:--:|:--:|
| 1. Mahsulotlar | 4 | 4 | 0 | 0 |
| 2. O'lcham | 4 | 4 | 0 | 0 |
| 3. Ombor/tayyorlik | 3 | 2 | 1 (3.2) | 0 |
| 4. Narx/chegirma | 2 | 2 | 0 | 0 |
| **Jami** | **13** | **12** | **1** | **0** |

## Xulosa

- **Konflikt yo'q.** Adminlar aytган hech narsa tizim mantig'iga zid emas (project shu biznes TZ'sidan qurilган).
- **Kritik biznes qoidalari to'liq mos:** "serkon toshi" (1.4), "Kumush 925 + rodiy" (1.3), o'lcham variant emas + bir narx (2.2/2.4), fixed narx + eski/yangi narx chegirmasi (4.1/4.2) — guardrail va model darajasида mustahkamlangan.
- **Bitta kichik bo'shliq (3.2):** "1 kunда tayyor" umumiy ma'lumoti strukturaviy maydonда emas. **Kod o'zgarishi shart emas** — bilim bazasiga (KB) yoki `settings`ga bir yozuv qo'shsa yetadi (AI shu ma'lumotни mijozga aytadi).
- **Data-only qadamlar (kodsiz):** real 12 ta mahsulotни `category` + `product` sifatida kiritish, `stock_qty` to'ldirish, "tayyorlik muddati" KB yozuvини qo'shish, asosiy to'lov kartasini `payment_card`ga yozish.
