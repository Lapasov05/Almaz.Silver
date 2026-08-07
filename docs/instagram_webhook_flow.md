# Instagram Webhook: Post, Reel, Story Linklash Oqimi

Bu hujjat Instagram webhookdan kelgan post, reel va story xabarlarini tizimdagi `SocialPost`, `CatalogItem`, `Conversation` va `Message` bilan qanday bog'lashni tushuntiradi. Shu arxitekturani boshqa projectga ham ko'chirish mumkin.

## Asosiy Maqsad

Mijoz Instagram DMga:

- oddiy text yozsa,
- storyga reply qilsa,
- storyni directga yuborsa,
- post/reelni directga yuborsa,
- ad/post/story referral orqali kirsa,

tizim shu xabar qaysi `SocialPost` yoki katalog mahsulotiga tegishli ekanini aniqlashi kerak. Aniqlansa conversation shu postga bog'lanadi. Aniqlanmasa xabar saqlanadi, lekin unga tizim izohi qo'shiladi.

## Asosiy Modellar

`SocialPost` media obyektni saqlaydi:

- `post_type`: `post`, `reel`, `story`, `ad`
- `media_id`: Instagram Graph API media id yoki fallback id
- `permalink`: Instagram permalink
- `instagram_username`: story linkdagi username
- `story_share_id`: story URLdagi share id
- `webhook_story_id`: webhook yoki Graph APIdan kelgan story idlar ro'yxati
- `webhook_story_url`: webhookdan kelgan temporary CDN URL
- `image_url`: post/story/reel preview rasmi

`CatalogItem` katalog mahsulotini saqlaydi:

- `social_post`: agar katalog mahsuloti post/story/reelga bog'langan bo'lsa
- `instagram_story_url`: agar katalog mahsulotiga story link qo'lda qo'yilgan bo'lsa

`InstagramWebhookEvent` raw webhookni audit/debug uchun saqlaydi:

- `event_type`
- `sender_id`
- `recipient_id`
- `message_id`
- `text`
- `media_id`
- `story_id`
- `story_url`
- `postback_referral`
- `extracted`
- `raw_payload`

`Conversation.social_post` mijoz suhbati qaysi media/katalogdan kelganini ko'rsatadi.

## Webhook Endpoint Oqimi

Endpoint:

```text
GET  /api/instagram/webhook/
POST /api/instagram/webhook/
```

`GET` verification uchun ishlaydi:

1. Instagram `hub.verify_token` yuboradi.
2. Tizim `IntegrationSettings.instagram_verify_token` yoki settingsdagi token bilan solishtiradi.
3. Token to'g'ri bo'lsa `hub.challenge` qaytariladi.

`POST` event qabul qilish uchun ishlaydi:

1. Request darhol `{"status": "EVENT_RECEIVED"}` qaytaradi.
2. Payload Celery taskga beriladi.
3. Task `resolve_instagram_event(payload)`ni chaqiradi.
4. Har bir saqlangan message uchun delayed AI reply task 7 sekunddan keyin ishga tushadi.

## Webhook Payloaddan Nima Olinadi

Webhook payload ichidagi muhim joylar:

```text
entry[].messaging[]
message.text
message.mid
message.attachments[]
message.reply_to
message.reply_to.story
message.referral
referral
sender.id
recipient.id
```

Tizim payloadni ikkita maqsadda parse qiladi:

1. Message text va attachment linklarini saqlash.
2. Xabar qaysi story/post/reelga tegishli ekanini aniqlash.

## Event Type Aniqlash

Event type quyidagicha belgilanadi:

| Holat | `event_type` |
|---|---|
| `message.attachments[].type == ig_story`, lekin `reply_to` yo'q | `story_send` |
| `message.reply_to` bor yoki payload ichida story belgisi bor | `story_reply` |
| Story bo'lmagan media attachment bor | `media_send` |
| Oddiy text | `message` |

## Story Attachment Payload

Mijoz storyni DMga yuborsa odatda attachment shunday keladi:

```json
{
  "message": {
    "mid": "mid-story-send-1",
    "attachments": [
      {
        "type": "ig_story",
        "payload": {
          "story_media_id": "18151925590500461",
          "story_media_url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=18151925590500461&signature=test"
        }
      }
    ]
  }
}
```

Tizim bundan oladi:

- `story_id`: `story_media_id`
- `media_id`: `story_media_id`
- `story_url`: `story_media_url`
- `event_type`: `story_send`

## Story Reply Payload

Mijoz storyga reply qilsa `message.reply_to` yoki `message.reply_to.story` kelishi mumkin:

```json
{
  "message": {
    "mid": "mid-story-reply-1",
    "text": "shu nechpul",
    "reply_to": {
      "story": {
        "id": "18151925590500461",
        "url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=18151925590500461&signature=test"
      }
    }
  }
}
```

Tizim bundan oladi:

- `story_id`: `reply_to.story.id`
- `media_id`: `reply_to.story.id`
- `story_url`: `reply_to.story.url`
- `event_type`: `story_reply`

## Post/Reel Share Payload

Mijoz post yoki reelni DMga yuborsa attachment story emas, oddiy media bo'ladi:

```json
{
  "message": {
    "mid": "mid-media-send-1",
    "attachments": [
      {
        "type": "share",
        "payload": {
          "url": "https://www.instagram.com/reel/SHORTCODE/",
          "ig_reel_media_id": "18000000000000000"
        }
      }
    ]
  }
}
```

Tizim media idni quyidagi keylardan qidiradi:

- `ig_post_media_id`
- `ig_reel_media_id`
- `reel_video_id`
- `reel_media_id`
- `media_id`
- `media_share_id`
- `media_product_id`
- `id`
- `source_id`
- `target_id`

URL quyidagi keylardan olinadi:

- `url`
- `media_url`
- `permalink`
- `link`
- `share_url`

## Referral Payload

Ad, post yoki storydan DM ochilsa `referral` kelishi mumkin:

```json
{
  "referral": {
    "media_id": "18000000000000000",
    "source_url": "https://www.instagram.com/p/SHORTCODE/"
  },
  "message": {
    "mid": "mid-referral-1",
    "text": "narxi qancha"
  }
}
```

Referraldan birinchi navbatda quyidagilar olinadi:

- `media_id`
- `source_id`
- `id`
- `source_url`
- `url`
- `link`
- `permalink`

## Media ID Olish Prioriteti

`media_id` quyidagi tartibda olinadi:

1. `referral.media_id`, `referral.source_id`, `referral.id`
2. `reply_to.media_id`, `reply_to.story_id`, `reply_to.id`
3. `reply_to.story.id`
4. story attachment: `story_media_id`, `media_id`, `id`
5. media attachment id
6. `story_url` ichidagi `asset_id`

`story_id` quyidagi tartibda olinadi:

1. `reply_to.story_id`, `reply_to.id`
2. `referral.story_id`
3. `reply_to.story.id`
4. story attachment: `story_media_id`, `story_id`, `id`
5. `story_url` ichidagi `asset_id`

`story_url` quyidagi tartibda olinadi:

1. `referral.source_url`, `referral.url`, `referral.link`, `referral.permalink`
2. `reply_to.url`, `reply_to.link`, `reply_to.permalink`
3. `reply_to.story.url`
4. story attachment: `story_media_url`, `url`, `media_url`
5. media attachment URL

## Link Normalizatsiya

Instagram linklar normalize qilinadi:

```text
https://www.instagram.com/reel/ABC/?igsh=xyz
```

quyidagiga aylanadi:

```text
https://www.instagram.com/reel/ABC
```

Ya'ni:

- query string olib tashlanadi,
- oxirgi `/` olib tashlanadi.

CDN lookaside URLdan `asset_id` olinadi:

```text
https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=18151925590500461&signature=test
```

`asset_id`:

```text
18151925590500461
```

Muhim qoida: lookaside base URLning o'zini match qilish xavfli. Faqat `asset_id` yoki to'liq normalized URL bilan match qilish kerak.

## SocialPost Match Qilish Tartibi

Webhook kelganda tizim avval `SocialPost`ni topishga harakat qiladi.

### 1. Media ID Bo'yicha Match

`media_id` yoki `story_id` quyidagi maydonlar bilan solishtiriladi:

- `SocialPost.media_id`
- `SocialPost.story_share_id`
- `SocialPost.webhook_story_id`
- `SocialPost.webhook_story_id contains media_id`

### 2. URL Bo'yicha Match

URL Instagram permalink bo'lsa:

- `SocialPost.permalink startswith normalized_url`
- `SocialPost.webhook_story_url startswith normalized_url`
- `CatalogItem.instagram_story_url startswith normalized_url`

URLda `asset_id` bo'lsa:

- `SocialPost.media_id == asset_id`
- `SocialPost.story_share_id == asset_id`
- `SocialPost.webhook_story_id contains asset_id`
- `SocialPost.webhook_story_url contains asset_id`
- `SocialPost.permalink contains asset_id`
- `CatalogItem.instagram_story_url contains asset_id`

## Story Linklash Algoritmi

Story uchun alohida kuchliroq algoritm bor.

1. Webhook event `story_reply` yoki `story_send` bo'lishi kerak.
2. `story_id = webhook_event.story_id or webhook_event.media_id`.
3. Agar `story_id` yo'q bo'lsa, `story_url`dan `asset_id` olinadi.
4. Avval exact match qilinadi: `social_post_by_media_or_url(story_id, story_url)`.
5. Topilsa:
   - `webhook_story_id`ga yangi story id qo'shiladi.
   - `webhook_story_url` yangilanadi.
   - shu `SocialPost` qaytariladi.
6. Topilmasa va `story_url` bor bo'lsa, Graph API orqali active stories ichidan story qidiriladi.
7. Graph API story topilsa:
   - `story.id`
   - `story.permalink`
   - `story.media_url`
   olinadi.
8. Graph API story permalink yoki id bo'yicha `SocialPost` qidiriladi.
9. Agar `SocialPost` topilmasa, `CatalogItem.instagram_story_url` bo'yicha katalog item qidiriladi.
10. Katalog item topilsa, undan avtomatik `SocialPost` yaratiladi va katalog itemga bog'lanadi.
11. Agar hech narsa topilmasa, lekin bazada webhook story id bo'sh bo'lgan faqat bitta active story post bo'lsa, fallback sifatida o'sha storyga bog'lanadi.
12. Agar candidate bir nechta bo'lsa, avtomatik bog'lanmaydi.

## Post/Reel Linklash Algoritmi

`media_send` uchun alohida oqim:

1. `media_id` bor bo'lsa, `SocialPost.media_id/story_share_id/webhook_story_id` bo'yicha exact match qilinadi.
2. Topilmasa Graph API recent media ichidan `media_id` bo'yicha media qidiriladi.
3. Graph API media topilsa, uning `permalink`i bilan `SocialPost` qidiriladi.
4. Topilgan `SocialPost.media_id` eski/fallback bo'lsa, real Graph media id bilan yangilanadi.
5. Agar webhookda URL bor bo'lsa, URL orqali `SocialPost` qidiriladi.
6. URL orqali ham topilmasa, `CatalogItem.instagram_story_url` yoki bog'langan social post URLlari orqali katalog item topiladi.
7. Katalog item topilsa, undan `SocialPost` yaratiladi.

## Qo'lda Link Qo'yilganda

Admin/tizim orqali `SocialPost.permalink` qo'yilganda serializer maydonlarni avtomatik to'ldiradi.

### Story Link

Link formati:

```text
https://www.instagram.com/stories/{username}/{story_share_id}/
```

Masalan:

```text
https://www.instagram.com/stories/euroflowers.uz/3948457236253594433/
```

Tizim quyidagilarni to'ldiradi:

- `instagram_username = euroflowers.uz`
- `story_share_id = 3948457236253594433`
- `post_type = story`
- `media_id = story-share-3948457236253594433`, agar media id berilmagan bo'lsa

Keyin token bor bo'lsa Graph API active stories ichidan shu permalink qidiriladi:

- topilsa `webhook_story_id = story.id`
- topilsa `webhook_story_url = story.media_url`
- `image_url` bo'sh bo'lsa va media URL qisqa bo'lsa, `image_url = story.media_url`

Story 24 soatdan keyin active storiesdan yo'qolishi mumkin. Shuning uchun link qo'yilgan paytda story hali active bo'lsa, `webhook_story_id`ni darhol saqlab olish muhim.

### Post Link

Link formati:

```text
https://www.instagram.com/p/{shortcode}/
```

Tizim Graph API recent media ichidan permalinkni topishga harakat qiladi:

- topilsa `media_id = media.id`
- `post_type = post`
- `image_url = media.media_url` yoki `thumbnail_url`

Topilmasa fallback:

- `media_id = post-link-{shortcode}`
- `post_type = post`

### Reel Link

Link formati:

```text
https://www.instagram.com/reel/{shortcode}/
```

Graph API recent media ichidan topilsa:

- `media_id = media.id`
- `media_type == video` bo'lsa `post_type = reel`
- `image_url = thumbnail_url` yoki `media_url`

Topilmasa fallback:

- `media_id = post-link-{shortcode}`
- `post_type = reel`

## Conversationga Bog'lash

Webhook message kelganda:

1. `sender.id` bo'yicha `Customer` topiladi yoki yaratiladi.
2. Shu customerning active conversationi qidiriladi.
3. Conversation yo'q bo'lsa yangi conversation yaratiladi va topilgan `SocialPost` bog'lanadi.
4. Conversation bor bo'lsa va yangi post topilgan bo'lsa:
   - `conversation.social_post` yangilanadi.
   - `conversation.branch` post branchiga o'tadi.
5. Agar mijoz media yuborgan bo'lsa, lekin tizim media/post/storyni aniqlay olmasa va eski conversation postga bog'langan bo'lsa:
   - `conversation.social_post = None`
   qilinadi.

Bu eski post konteksti yangi noma'lum media xabariga noto'g'ri ulanib qolmasligi uchun kerak.

## Message Text va Metadata

Webhookdan kelgan attachment URLlar message textga qo'shiladi:

```text
Mijoz Instagram storyni directga yubordi.
Story link: https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=...
```

Metadata ichida ham saqlanadi:

```json
{
  "attachments": [
    {
      "kind": "story",
      "type": "ig_story",
      "url": "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=...",
      "source": "instagram_attachment"
    }
  ]
}
```

Agar media bazadagi post/story/reelga bog'lanmasa, message textga tizim izohi qo'shiladi:

```text
Tizim izohi: yuborilgan Instagram media bazadagi story/post/reel katalogiga bog'lanmagan.
```

## Katalogdan SocialPost Yaratish

Ba'zan katalog itemga `instagram_story_url` qo'yilgan bo'ladi, lekin alohida `SocialPost` hali yaratilmagan bo'ladi.

Webhook kelganda:

1. Story URL yoki permalink bo'yicha `CatalogItem` topiladi.
2. Agar `CatalogItem.social_post` yo'q bo'lsa, avtomatik `SocialPost` yaratiladi.
3. Yangi `SocialPost`:
   - katalog item branchini oladi,
   - post type URLdan aniqlanadi,
   - media id webhookdan yoki fallbackdan olinadi,
   - title/description/price/image katalogdan olinadi.
4. `CatalogItem.social_post` shu postga bog'lanadi.

## Deduplikatsiya

Bir xil media ikki marta kiritilmasligi uchun:

- `media_id` unique bo'lishi kerak.
- `permalink` normalized ko'rinishda unique tekshiriladi.
- Agar media id allaqachon boshqa `SocialPost`da bo'lsa, yangi post yaratilmaydi.
- Agar permalink allaqachon boshqa postda bo'lsa, serializer validation error beradi.

## Debug Uchun Loglar

Webhook saqlanganda console log chiqadi:

```text
INSTAGRAM_WEBHOOK_EVENT id=... type=... sender=... mid=... media_id=... story_id=... story_url=...
```

Story linklanganda:

```text
INSTAGRAM_STORY_LINKED social_post_id=... story_id=... active_story_id=... webhook_event_id=...
```

Graph API lookup xato qilsa:

```text
INSTAGRAM_ACTIVE_STORY_LOOKUP_FAILED webhook_event_id=... error=...
```

Bu loglar productionda webhookni tez debug qilish uchun juda muhim.

## Boshqa Projectga Ko'chirish Uchun Minimal Algoritm

1. Raw webhook eventni doim alohida jadvalga saqla.
2. Payload ichidan `text`, `sender_id`, `message_id`, `referral`, `reply_to`, `attachments`ni ajrat.
3. Story attachment va oddiy media attachmentni alohida parse qil.
4. `media_id`, `story_id`, `story_url`ni yuqoridagi priority bo'yicha top.
5. Event typeni aniqlab ol: `message`, `story_send`, `story_reply`, `media_send`.
6. Linklarni normalize qil: query string va oxirgi slashni olib tashla.
7. lookaside URLdan faqat `asset_id`ni match key sifatida ishlat.
8. Avval exact id bo'yicha match qil, keyin permalink bo'yicha.
9. Story uchun Graph API active stories lookup qo'sh.
10. Post/reel uchun Graph API recent media lookup qo'sh.
11. Bitta aniq candidate bo'lmasa avtomatik linklama.
12. Conversationni topilgan postga bog'la.
13. Topilmagan media uchun messagega tizim izohi qo'sh.
14. Attachment URLlarni metadata ichida saqla.
15. AI replyni darhol emas, qisqa delay bilan ishga tushir.

## Tavsiya Qilingan Schema

Minimal `SocialPost`:

```text
id
branch_id
post_type
media_id unique
permalink
instagram_username
story_share_id
webhook_story_id text
webhook_story_url text
title
description
price
image_url
is_active
created_at
updated_at
```

Minimal webhook event:

```text
id
event_type
sender_id
recipient_id
message_id
text
media_id
story_id
story_url
postback_referral json
extracted json
raw_payload json
created_at
```

Minimal conversation:

```text
id
customer_id
branch_id
social_post_id nullable
status
last_message_at
created_at
updated_at
```

## Xavfsiz Match Qoidalari

- Faqat `lookaside.fbsbx.com/ig_messaging_cdn/` base URL bilan match qilma.
- `asset_id` bo'lmasa lookaside URLni ishonchli key deb hisoblama.
- Story fallbackni faqat bitta aniq active story candidate bo'lsa ishlat.
- `webhook_story_id` bir nechta idni saqlashi mumkin, chunki Instagram webhook va Graph API idlari har doim bir xil bo'lmasligi mumkin.
- Story hali active bo'lgan paytda Graph APIdan real story id va media URLni olib saqlab qo'y.
- Post/reel link qo'lda qo'yilganda Graph APIdan real `media_id`ni olishga harakat qil.
- Graph API ishlamasa fallback id ishlat, lekin keyin webhook kelganda real id bilan yangilash imkonini qoldir.
- Oldingi conversation postini noma'lum yangi media bilan davom ettirma; media topilmasa `conversation.social_post`ni tozala.

## Projectdagi Asosiy Fayllar

- `backend/core/views.py`: webhook endpoint.
- `backend/core/tasks.py`: async webhook processing va delayed AI reply.
- `backend/core/webhook_services.py`: payload parse, event save, post/story/reel matching.
- `backend/core/platform_services.py`: Instagram Graph API helperlar.
- `backend/core/serializers.py`: qo'lda permalink qo'yilganda `SocialPost` maydonlarini to'ldirish.
- `backend/core/models.py`: `SocialPost`, `CatalogItem`, `InstagramWebhookEvent`, `Conversation`.
- `backend/core/tests.py`: story reply, story send, unmatched media, active story lookup testlari.

## Ideal Test Case Ro'yxati

Har projectda quyidagi testlar bo'lishi kerak:

1. Webhook verification token to'g'ri bo'lsa challenge qaytadi.
2. Story attachment kelganda message textga `Story link` qo'shiladi.
3. Story reply `reply_to.story.url` orqali mavjud `SocialPost`ga bog'lanadi.
4. Story CDN URLdagi `asset_id` Graph API active story orqali permalinkga ulanadi.
5. Katalog itemda faqat `instagram_story_url` bo'lsa, webhook kelganda `SocialPost` avtomatik yaratiladi.
6. Boshqa storyning lookaside base URLi eski storyga noto'g'ri match bo'lmaydi.
7. Post/reel media id bo'yicha mavjud `SocialPost` topiladi.
8. Post/reel permalink bo'yicha fallback match ishlaydi.
9. Media topilmasa conversation eski `social_post`dan uziladi.
10. Duplicate `media_id` va duplicate `permalink` bloklanadi.
