# INTEGRATIONS.md — loyihaga qo'shildi (migratsiya `0014`)

> `docs/INTEGRATIONS.md` (referens) dagi naqsh shu loyihaga moslab qo'shildi + siz so'ragan
> **boshlang'ich AI salom** ishga tushdi. **Tekshirildi — 14/14 test.**

Loyihада webhook/normalize/async-AI/dispatch **allaqachon bor edi** (Faza 2). Qo'shilgani:

## 1. DB-driven token — `IntegrationConfig`
Tokenlar endi kodda emas, `(provider, key) → value` jadvalида. Admin API orqali almashtiradi —
**deploy shart emas**, keyingi so'rov avtomatik yangi qiymatni oladi.

```
GET    /integrations/configs?provider=telegram     (pagination)
POST   /integrations/configs   {provider, key, value, is_active}   # (provider,key) upsert
PATCH  /integrations/configs/{id}
DELETE /integrations/configs/{id}
```
**Token o'qish tartibi:** IntegrationConfig (DB, aktiv) → `.env` (settings) → default. Ya'ni
`.env` fallback saqlanadi — hech narsa buzilmaydi. Kalitlar: `telegram/bot_token`,
`telegram/webhook_secret`, `instagram/access_token`, `instagram/verify_token`, `instagram/app_secret`, `openai/api_key`.

Webhook verify (secret / app_secret / verify_token) va outbound send (bot_token / access_token) endi
shu tartibда tokenni oladi.

## 2. `IntegrationEvent` — xom payload audit
Har kelgan webhook payload (parse qilinsa ham, qilinmasa ham) saqlanadi — «nega bu xabar ishlanmadi»
degan savolga javob.
```
GET /integrations/events?provider=telegram&status=received   (pagination)
```

## 3. Webhook setup helperlari (bir martalik)
```
POST /integrations/telegram/set-webhook   {url}     # setWebhook (secret DB'dan)
GET  /integrations/telegram/webhook-info
GET  /integrations/telegram/me                       # qaysi bot ulangan
POST /integrations/telegram/delete-webhook
POST /integrations/instagram/subscribe               # me/subscribed_apps (MAJBURIY qadam)
```
Hammasi `settings:manage_integrations` bilan.

## 4. ⭐ Boshlang'ich AI salom (siz so'ragan — hozir ishlaydi)
Mijoz TG/IG'дан yozganда, **LLM hali ulanmagan bo'lsa ham**, birinchi xabarga **boshlang'ich salom**
yuboriladi. Keyin (tool'lar qo'shilganда) to'liq agent ishlaydi.

- Matn: Settings `ai_greeting_text` (o'zgartirsangiz bo'ladi): `PUT /settings/ai_greeting_text`.
- Mantiq: `conversation.ai_state == greeting` (birinchi xabar) → salom yuboriladi → holat `browsing`.
  **Faqat bir marta** — keyingi xabarlar (LLM yo'q bo'lsa) takrorlamaydi.
- OpenAI ulanганда (`OPENAI_API_KEY`): to'liq agent javob beradi (salom system prompt orqali).

## 5. Markdown tozalash
Chiquvchi xabarda `**bold**`, `` `kod` ``, `# sarlavha` kabi markdown **oddiy matnга** aylantiriladi
(TG/IG render qilmaydi) — bitta markazlashgan joyda (`strip_markdown`).

## Topilgan/tuzatilgan bug
`IntegrationConfig` UPDATE'дан keyin `updated_at` (server `onupdate`) expired bo'lib, javob
serializatsiyasida **MissingGreenlet (500)** berardi → commit'дан keyin `refresh` qo'shildi.

## O'zgargan fayllar
`integrations/` (yangi modul: models, schemas, repository, service, router) ·
`inbox/channels/{base,telegram,instagram,factory}.py` (DB-token + markdown) ·
`inbox/{service,webhooks}.py` (DB-token, event audit) · `ai/agent.py` (salom) ·
`notifications/service.py` · `settings/defaults.py` (ai_greeting_text) · `main.py`, `migrations/env.py` ·
`migrations/versions/0014_integrations.py`

## Tekshirildi: 14/14
markdown · config upsert/re-upsert/list/delete · webhook DB-secret (noto'g'ri→401, to'g'ri→200) ·
integration_event audit · DB-token .env ustidan ustun + fallback · **boshlang'ich salom yuborildi
(state→browsing, AI xabari saqlandi)** · 2-xabarда takrorlanmaydi.

## Sozlash (deploy)
```bash
git pull && docker compose up -d --build   # 0014 migratsiya avtomatik
# tokenlarni .env yoki API orqali qo'ying:
POST /integrations/configs {"provider":"telegram","key":"bot_token","value":"<token>"}
POST /integrations/telegram/set-webhook {"url":"https://almaz.api.cognilabs.org/webhooks/telegram"}
```
> Keyingi qadamlar (siz aytgandek): tool'lar va boshqa ketma-ketliklar — OpenAI ulanганда agent to'liq ishlaydi.
