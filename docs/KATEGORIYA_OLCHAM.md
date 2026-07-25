# Kategoriyalar + o'lcham (migratsiya `0013`)

> Admin javobi (25.07): kategoriyalar — **uzuk, braslet, sepochka, zirak, komplekt** (uzuk+zirak+sepochka).
> «Uzukdan tashqari qolgan mahsulotlar universal (hamma razmerga tushadi)» — ya'ni **faqat uzukда o'lcham** bor.
> **Holat: tekshirildi va moslandi — 11/11 test.**

---

## Avvaldan to'g'ri edi
O'lcham (`ring_size`) allaqachon **buyurtma darajasида** (`order_item.ring_size`) va **ixtiyoriy** —
universal mahsulotlar (braslet/sepochka/zirak/komplekt) o'lchamsiz buyurtma qilinadi, uzuk o'lcham bilan.
Bu ishlar edi.

## Qo'shildi: `requires_ring_size` bayrog'i
Kamchilik: AI (va frontend) qaysi mahsulot o'lcham so'rashini aniq bilmasdi — faqat nom bo'yicha taxmin qilardi.
Endi **kategoriya darajasида** aniq bayroq bor:

| Qatlam | Maydon | Ma'nosi |
|---|---|---|
| `category` | **`requires_ring_size`** (bool) | Bu kategoriya mahsulotida o'lcham bo'ladimi. **Uzuklar = true**, qolganlari **false**. |
| `product` (javob) | `requires_ring_size` | Kategoriyadan olinadi — buyurtmada o'lcham kerakmi. |
| AI tool brief | `requires_ring_size` | AI shu bo'yicha o'lcham so'raydi yoki so'ramaydi. |

- **AI xulqi:** brief'да `requires_ring_size=true` → o'lchamni so'raydi (sovg'a bo'lsa o'rta o'lcham/ip).
  `false` → o'lcham SO'RAMAYDI (universal). System prompt shunga moslandi.
- **Frontend:** buyurtma oynasida o'lcham maydonini faqat `requires_ring_size=true` mahsulotга ko'rsatsin.
- Migratsiya mavjud «Uzuklar» (uz) / «Кольца» (ru) kategoriyalarini avtomatik `true` qiladi.

## Kategoriyani boshqarish
```bash
# Uzuklar kategoriyasi — o'lchamli
POST /catalog/categories {"name_uz":"Uzuklar","name_ru":"Кольца","requires_ring_size":true}
# Zirak/braslet/sepochka/komplekt — universal (default false)
POST /catalog/categories {"name_uz":"Ziraklar","name_ru":"Серьги"}
# mavjudini o'zgartirish
PATCH /catalog/categories/{id} {"requires_ring_size":true}
```

demo_seed endi **5 kategoriya**: Uzuklar (o'lchamli), Brasletlar, Sepochkalar, **Ziraklar** (yangi), Komplektlar.

## Yo'l-yo'lakay tuzatilgan 2 bug (test topdi)
1. `CatalogService.create_category` yangi `requires_ring_size` ni modelga o'tkazmayotgan edi (default false qolardi).
2. AI tool brief'да o'chirilgan `product.weight_grams` ga havola qolgan edi → AI qidiruv/tafsilotда
   **AttributeError** berardi (avvalgi 0011 o'zgarishidan qolgan). Endi `requires_ring_size` bilan almashtirildi.

## O'zgargan fayllar
`catalog/{models,schemas,service,repository}.py` · `ai/{tools,prompts}.py` · `demo_seed.py` ·
`migrations/versions/0013_category_requires_size.py`

## Tekshirildi: 11/11
5 kategoriya (Ziraklar) · Uzuklar=true, qolgan=false · mahsulot va AI brief'да to'g'ri ·
brief'да weight_grams yo'q · uzuk buyurtma o'lcham bilan, zirak o'lchamsiz.

## Deploy
```bash
git pull && docker compose up -d --build   # 0013 migratsiya avtomatik (Uzuklar -> requires_ring_size=true)
```
