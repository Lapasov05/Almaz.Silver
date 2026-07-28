# Frontend — Instagram post/story ↔ mahsulot

> Migratsiya `0018`. Jonli Postgres smoke: **14/14**.
> Mijoz IG **post/story link** tashlasa yoki bizning **story'ga javob** bersa — AI mahsulotni bazadan
> topib, zaxirani tekshirib, sotuvni davom ettiradi. Admin har mahsulotga **link qo'yib** post/story biriktiradi.

## Umumiy
- **Auth:** `Bearer <token>`. Ruxsat: `products:*`.
- Bitta mahsulotga **bir nechta post VA story** biriktiriladi.
- **Story 24 soat** turadi (`expires_at`); post/reel — doimiy.
- Xato: `4xx` + `{"detail": "..."}`.

## 1. Admin — "Instagram" bo'limi (link qo'yish)

Admin faqat **link qo'yadi**; sistema turini (post/reel/story) va ref'ini avtomatik ajratadi.

| Method | Path | Body | Javob |
|---|---|---|---|
| POST | `/catalog/products/{product_id}/instagram` | `{ "link": "...", "image_url"?: "..." }` | `InstagramMediaOut` |
| GET | `/catalog/products/{product_id}/instagram` | — | `InstagramMediaOut[]` (post+story) |
| PATCH | `/catalog/instagram-media/{media_id}` | `{ "is_active"?: bool, "image_url"?: "..." }` | `InstagramMediaOut` |
| DELETE | `/catalog/instagram-media/{media_id}` | — | `204` |

**Qabul qilinadigan linklar:**
- Post/Reel: `https://www.instagram.com/p/<shortcode>/` · `/reel/<shortcode>/` · `/tv/<shortcode>/`
- Story: `https://www.instagram.com/stories/<username>/<media_id>/`
- (Toza `shortcode` yoki `story_ref` ham bo'ladi.)

Noto'g'ri link → `400 "Instagram post yoki story linki noto'g'ri"`.

**InstagramMediaOut:**
```json
{
  "id": "uuid",
  "product_id": "uuid",
  "media_type": "post",          // post | reel | story
  "shortcode": "Cabc123_-",       // post/reel uchun
  "story_ref": null,              // story uchun (media_id)
  "permalink": "https://www.instagram.com/p/Cabc123_-/",
  "image_url": null,
  "is_active": true,
  "is_expired": false,            // story muddati o'tganmi
  "expires_at": null,             // story uchun ~24 soat; post = null
  "created_at": "2026-07-28T10:00:00Z"
}
```

### Frontend TODO (admin)
- Mahsulot sahifasida **"Instagram"** bo'limi: link input + "Qo'shish"; ro'yxat (post/story ajratib,
  `permalink`ga havola, `image_url` bo'lsa thumbnail); `is_active` toggle; o'chirish.
- Story qatorida `is_expired=true` bo'lsa "muddati o'tgan" belgisi (yangilash uchun yangi link qo'yish kerak).

## 2. AI oqimi (avtomatik — frontend faqat inbox'da ko'radi)
- Mijoz IG **post/story link** yozsa yoki **story'ga javob** bersa → AI `resolve_instagram_media` bilan
  mahsulotni topadi → **zaxirada bo'lsa** o'sha mahsulot bo'yicha savdo; **topilmasa** mijozdan so'raydi;
  **tugagan bo'lsa** muloyim aytadi + o'xshashini taklif qiladi.
- Story javoblari webhook orqali keladi (`reply_to.story.id`), inbox'da oddiy xabar sifatida ko'rinadi;
  AI javobi ham o'sha suhbatda. Frontend uchun qo'shimcha ish yo'q — mavjud inbox'da ko'rinadi.

## Demo
```bash
make demo-seed
make demo-instagram   # mahsulotlarga demo post+story link
# GET /catalog/products/{id}/instagram
```

## Tekshirildi: 14/14 (jonli Postgres)
webhook story-javob parse · admin post/story qo'shish (shortcode/story_ref/expires) · list · resolve
(post/story/ref) · muddati o'tgan story→topilmaydi · AI resolve tool (found/none) · agent kontekst
(story-javob + matndagi link) · update/delete · demo (idempotent).
