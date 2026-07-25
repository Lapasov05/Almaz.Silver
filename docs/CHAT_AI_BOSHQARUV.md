# Suhbatда AI'ni boshqarish (migratsiya `0012`)

> Muammo: operator suhbatni o'zига olib, yozib, buyurtmani chiqargandan keyin — AI faqat 15 daqiqaga
> jimадi. Mijoz ertaga yozsa, AI yana o'zi javob berib yuboradi. Kerak: operator shu suhbatда AI'ni
> **istagan vaqtgacha (daqiqa yoki aniq sana-vaqt)** yoki **butunlay** o'chirib qo'yishi.
> **Holat: bajarildi va tekshirildi — 10/10 test.**

---

## Qanday ishlaydi

Har suhbat (`conversation`) da endi 2 ta boshqaruv bor:
| Maydon | Ma'nosi |
|---|---|
| `ai_enabled` (yangi) | Shu suhbatда AI umuman javob bersinmi. `false` — **butunlay o'chiq** (mijoz keyin yozsa ham AI jim). |
| `ai_paused_until` | AI shu vaqtgacha jim (vaqtinchalik pauza). |

**Agent gating tartibi:** global `ai_enabled` (Settings) → suhbat `ai_enabled` → `closed` → `ai_paused_until > hozir`.

## Endpoint — bitta joydan boshqariladi

```
POST /inbox/conversations/{id}/ai        (conversations:update)
```
`mode` ga qarab:

| mode | Body | Natija |
|---|---|---|
| `pause_minutes` | `{"mode":"pause_minutes","minutes":15}` | AI shu suhbatда **N daqiqaga** jimadi |
| `pause_until` | `{"mode":"pause_until","until":"2026-07-27T09:00:00Z"}` | AI **aniq sana-vaqtgacha** jimadi |
| `off` | `{"mode":"off"}` | AI **butunlay o'chiriladi** (indefinite — operator o'zi yuritadi) |
| `on` | `{"mode":"on"}` | AI **yoqiladi** (pauza ham tozalanadi) |

Namuna:
```bash
# operator suhbatni o'ziga olib bo'ldi -> AI'ni 3 kunga o'chirsin (sana bilan):
curl -X POST .../inbox/conversations/<id>/ai -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"mode":"pause_until","until":"2026-07-27T09:00:00Z"}'

# yoki butunlay o'chir:
-d '{"mode":"off"}'
# keyin qайта yoqish:
-d '{"mode":"on"}'
```

`GET /inbox/conversations` javobida endi `ai_enabled` va `ai_paused_until` bor — front holatni ko'rsatadi.

## Settingsdan boshqariladigan qism

- **`ai_pause_minutes`** (default 15) — operator **oddiy xabar yozganда** avtomatik pauza muddati.
  O'zgartirish: `PUT /settings/ai_pause_minutes {"value": 30}`.
- **`ai_enabled`** (global) — butun tizim bo'yicha AI'ni yoqish/o'chirish.
- Operator xabar yozsa: avvalgidek `ai_paused_until = now + ai_pause_minutes` (vaqtinchalik).
  **Uzoq/butunlay** o'chirish uchun esa yuqoridagi `/ai` endpoint (`pause_until` yoki `off`).

## Farqi (muhim)
- **Oddiy pauza** (operator yozsa) — vaqtinchalik (15 daq), keyin AI o'zi qaytadi. Bu sizning muammoyingiz edi.
- **`off` / `pause_until`** — operator ataylab qo'yadi; mijoz ertaga yozsa ham AI **jim qoladi**, faqat operator ishlaydi. `on` bilan qaytariladi.

## O'zgargan fayllar
`inbox/models.py` (ai_enabled) · `inbox/schemas.py` (AiControlRequest, ConversationOut) ·
`inbox/service.py` (set_ai_control) · `inbox/router.py` (POST /ai) · `ai/agent.py` (gating) ·
`migrations/versions/0012_conv_ai_enabled.py`

## Tekshirildi: 10/10
default ai_enabled=true · AI ochiq→javob · **off→jim** (ai_disabled_conversation) · on→javob ·
pause_minutes(15)≈900s→jim · **pause_until(3 kun)→jim** · o'tgan sana→rad ·
operator yozsa pauza qo'yiladi, ai_enabled o'zgarmaydi.

## Deploy
```bash
git pull && docker compose up -d --build     # 0012 migratsiya avtomatik
```
