# Telegram va Instagram integratsiyasi — texnik hujjat

Boshqa loyihada qayta qo'llash uchun referens. Ikkala integratsiya ham bir xil
arxitekturaga quriladi: **DB-driven config + webhook + normalize + async AI +
dispatch**. Hardcode token yo'q — hammasi bitta jadvalda.

---

## 1. Asosiy g'oya: `IntegrationConfig` — markazlashgan sozlama jadvali

```python
class IntegrationConfig(models.Model):
    class Provider(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        INSTAGRAM = "instagram", "Instagram"
        OPENAI = "openai", "OpenAI"

    provider = models.CharField(max_length=32, choices=Provider.choices)
    key = models.CharField(max_length=120)       # masalan "bot_token", "access_token"
    value = models.TextField(blank=True)          # haqiqiy qiymat (token)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("provider", "key")
```

Har bir token/kalit — bitta qator: `(provider, key) -> value`. Kodda token
**hech qachon** yozilmaydi, faqat shu jadvaldan o'qiladi:

```python
def get_integration_value(provider: str, key: str, default: str = "") -> str:
    config = IntegrationConfig.objects.filter(provider=provider, key=key, is_active=True) \
        .order_by("-updated_at").first()
    return config.value if config else default
```

**Nega bu muhim:** admin panel/API orqali (`/api/settings/integrations/`) token
almashtirilganda **kod deploy qilish shart emas** — keyingi so'rov avtomatik
yangi qiymatni o'qiydi.

### Kerakli kalitlar (loyihada ishlatilgan)
| provider | key | Nima uchun |
|---|---|---|
| `telegram` | `bot_token` | Bot API chaqiruvlari uchun |
| `telegram` | `webhook_secret` | (ixtiyoriy) webhook so'rovini tasdiqlash |
| `instagram` | `access_token` | Xabar yuborish uchun (Graph API) |
| `instagram` | `verify_token` | Webhook GET-handshake tasdiqlash |
| `instagram` | `app_secret` | Webhook POST imzosini (`X-Hub-Signature-256`) tekshirish |
| `instagram` | `business_id` | (ixtiyoriy, hozirgi oqimda ishlatilmaydi) |

---

## 2. Umumiy oqim (ikkalasi ham bir xil naqsh)

```
Telegram/Instagram serveri
        │  webhook POST (yangi xabar)
        ▼
  Webhook View (AllowAny, auth yo'q)
        │  1) imzo/token tekshiruv (ixtiyoriy)
        │  2) IntegrationEvent yozuvi (xom payload — audit/debug uchun)
        │  3) parse -> {platform_user_id, message, title}
        ▼
  enqueue_inbound_message() — ChatSession + ChatMessage yaratadi/topadi
        │
        ▼
  Celery task (5 soniya kechikish bilan) -> AI javob generatsiyasi
        │
        ▼
  deliver_outbound_message() — javobni platformaga qaytarib yuboradi
```

**Muhim dizayn qarorlari:**
- Webhook endpoint **har doim tezkor javob qaytaradi** (200/202), AI generatsiyasi
  **Celery orqali asinxron** — messenjer serveri webhookni kutib qolmaydi va
  qayta-qayta retry qilmaydi.
- `IntegrationEvent` — **har bir kelgan xom payload saqlanadi** (parse qilinsa
  ham, qilinmasa ham). Bu debug va audit uchun oltin qiymatga ega — "nega bu
  xabar ishlanmadi" degan savolga har doim javob topiladi.
- Ikkala platforma ham **bitta umumiy modelga** (`ChatSession`/`ChatMessage`)
  normalize qilinadi — AI/CRM logikasi platformadan bexabar ishlaydi.

---

## 3. Telegram — ulanish logikasi

### 3.1. Webhook o'rnatish (bir martalik, deploy/ngrok o'zgarganda)
```python
def set_webhook(url: str, secret_token: str = "") -> dict | None:
    payload = {"url": url, "allowed_updates": ["message", "edited_message"]}
    if secret_token:
        payload["secret_token"] = secret_token
    return _call("setWebhook", payload)   # POST https://api.telegram.org/bot<token>/setWebhook
```
Amalda: `bot_token`ni DB'dan o'qib, Telegram Bot API'ga `setWebhook` chaqiriladi.
`url` — loyihangizning ochiq (https, masalan ngrok) manzili + webhook path.

### 3.2. Webhook qabul qilish
```python
class TelegramWebhookView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = get_integration_value("telegram", "webhook_secret", "")
        if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != secret:
            return Response({"message": "invalid secret"}, status=403)
        session = handle_telegram_update(request.data or {}, process_inline=False)
        return Response({"status": "success", "data": {"session_id": ...}})
```
- `AllowAny` + **auth yo'q** — bu tashqi tomondan keladigan webhook, JWT bo'lishi
  mumkin emas. Xavfsizlik **secret token** (Telegram) yoki **HMAC imzo**
  (Instagram, pastga q.) orqali ta'minlanadi.
- `webhook_secret` ixtiyoriy, lekin production'da **tavsiya etiladi** — aks
  holda webhook URL'ni bilgan har kim soxta update yubora oladi.

### 3.3. Update'ni normalize qilish
```python
def parse_telegram_update(update: dict) -> dict | None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None
    text = message.get("text") or message.get("caption") or ""
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None or not text.strip():
        return None
    sender = message.get("from") or {}
    name = " ".join(p for p in [sender.get("first_name",""), sender.get("last_name","")] if p).strip()
    title = name or sender.get("username","") or f"telegram:{chat_id}"
    return {"platform_user_id": str(chat_id), "message": text.strip(), "title": title}
```
Telegramning xom JSON strukturasi (`message.chat.id`, `message.from.first_name`...)
umumiy `{platform_user_id, message, title}` shakliga tushiriladi — bu format
Instagram uchun ham bir xil, shuning uchun keyingi barcha kod (session, AI)
platformani bilmaydi.

### 3.4. Xabar yuborish (outbound)
```python
def send_telegram_message(chat_id, text: str) -> dict | None:
    return _call("sendMessage", {"chat_id": chat_id, "text": text})
    # POST https://api.telegram.org/bot<token>/sendMessage
```

### 3.5. Kerakli boshqa Bot API metodlari (tayyor helper'lar)
`get_webhook_info()`, `delete_webhook()`, `get_me()` (bot identifikatsiyasi —
qaysi bot ulanganini tekshirish uchun), `get_updates()` (long-polling — Celery/
webhook yo'q lokal ishlab chiqish uchun muqobil).

---

## 4. Instagram — ulanish logikasi (Meta Graph API, "Instagram Login" oqimi)

⚠️ **Muhim farq:** Bu yerda **`graph.instagram.com`** ishlatiladi (IGAA... token
bilan), **`graph.facebook.com`** emas. Bular ikkita boshqa integratsiya oqimi —
aralashtirmaslik kerak (eski "Facebook Page orqali Messenger" oqimi boshqacha).

```python
GRAPH_API_BASE = "https://graph.instagram.com/v21.0"
```

### 4.1. Webhook GET — handshake (bir martalik, Meta dashboard sozlaganda)
Meta konsolga webhook URL kiritilganda, Meta **GET** so'rov yuboradi va sizning
serveringiz uni tasdiqlashi kerak:

```python
def verify_subscription(mode: str, token: str, challenge: str):
    expected = get_verify_token()   # DB'dagi instagram.verify_token
    if mode == "subscribe" and expected and token == expected:
        return challenge            # aynan shu qiymatni qaytarish kerak
    return None
```
```python
class InstagramWebhookView(GenericAPIView):
    def get(self, request):
        mode = request.query_params.get("hub.mode", "")
        token = request.query_params.get("hub.verify_token", "")
        challenge = request.query_params.get("hub.challenge", "")
        verified = verify_subscription(mode, token, challenge)
        if verified is None:
            return Response({"message": "verification failed"}, status=403)
        return HttpResponse(verified, content_type="text/plain")   # RAW matn, JSON EMAS
```
**Diqqat:** javob **plain text** bo'lishi shart (`HttpResponse`, DRF `Response`
emas) — Meta buni JSON deb kutmaydi, faqat challenge qiymatini o'qiydi.

`verify_token` — o'zingiz DB'ga (yoki `.env`ga) o'rnatgan ixtiyoriy matn (masalan
`:killer;`), Meta konsolida ham xuddi shu qiymat kiritiladi.

### 4.2. Webhook POST — xabar imzosini tekshirish (HMAC)
```python
def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    app_secret = get_app_secret()
    if not app_secret:
        return True   # sozlanmagan bo'lsa — tekshiruv o'chirilgan
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]   # "sha256=<hex>"
    return hmac.compare_digest(expected, provided)
```
Bu Instagram/Telegramning **umumiy xavfsizlik farqi**: Telegram — bitta secret
header solishtiradi, Meta — butun so'rov body'sining HMAC-SHA256 imzosini
tekshiradi (`X-Hub-Signature-256` header). Loyihada imzo mos kelmasa **log
yoziladi, lekin so'rov baribir qayta ishlanadi** (setup bosqichida app_secret
noto'g'ri sozlanishi mumkinligi uchun) — production'da buni qat'iy 403'ga
aylantirish tavsiya etiladi.

### 4.3. Payload'ni normalize qilish
```python
def parse_instagram_events(payload: dict) -> list[dict]:
    results = []
    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            message = event.get("message") or {}
            if message.get("is_echo"):
                continue   # botning o'zi yuborgan xabarni e'tiborsiz qoldirish (loop oldini olish!)
            text = message.get("text") or ""
            sender = (event.get("sender") or {}).get("id")
            if not sender or not text.strip():
                continue
            results.append({"platform_user_id": str(sender), "message": text.strip(), ...})
    return results
```
**`is_echo` tekshiruvi kritik** — Meta business akkaunt o'zi yuborgan xabarni
ham webhook orqali qaytarib yuboradi; buni filtrlamasangiz, bot **o'z-o'ziga
javob berib, cheksiz loop**ga tushib qolishi mumkin.

### 4.4. Xabar yuborish (outbound)
```python
def send_instagram_message(recipient_id, text: str):
    url = f"{GRAPH_API_BASE}/me/messages"   # "me" — token o'z egasi akkaunt
    httpx.post(url, params={"access_token": token},
               json={"recipient": {"id": recipient_id}, "message": {"text": text}})
```

### 4.5. Meta tomonidagi sozlash (dashboard, kod emas)
1. Meta App yaratish → "Instagram API with Instagram Login" mahsulotini qo'shish.
2. Webhook URL: `https://<domen>/webhooks/instagram/`, Verify token: DB'даgi qiymat.
3. **Obuna majburiy** (ko'p odam shu joyda adashadi): App sozlangandan keyin
   akkauntni webhook eventlariga obuna qilish kerak —
   `POST https://graph.instagram.com/v21.0/me/subscribed_apps?access_token=<token>`
   Aks holda webhook sozlangan bo'lsa ham **xabar hech qachon kelmaydi**.

---

## 5. Chiquvchi xabar — platformaga qarab yo'naltirish (dispatcher)

```python
def deliver_outbound_message(session, text: str):
    text = strip_markdown(text)              # ** va # kabi belgilar oddiy matn qiladi
    if session.platform == "telegram":
        return send_telegram_message(session.platform_user_id, text)
    if session.platform == "instagram":
        return send_instagram_message(session.platform_user_id, text)
    return None   # web-chat: push shart emas, frontend GET/WebSocket bilan o'qiydi
```
**Nega markdown tozalanadi:** AI/LLM javobida ko'pincha `**muhim**` kabi
markdown chiqadi. Telegram/Instagram buni **oddiy matn** sifatida ko'rsatadi
(`**muhim**` — yulduzchalar bilan birga), render qilmaydi. Shuning uchun har
chiquvchi xabarda majburiy tozalash bosqichi bor.

Bu funksiya **bitta joydan** (masalan `chats/services.py`даgi "AI/operator xabar
yaratildi" hodisasidan) chaqiriladi — CRM/AI kodi qaysi platformaga yuborishni
bilishi shart emas, `session.platform` maydoniga qarab dispatcher o'zi hal qiladi.

---

## 6. URL marshrutlash — muhim tuzoq

```python
router = DefaultRouter()
router.register("events", IntegrationEventViewSet, basename="integration-events")
router.register("", IntegrationConfigViewSet, basename="integration-configs")   # catch-all OXIRIDA

urlpatterns = [
    path("", include(router.urls)),
    path("webhooks/telegram/", TelegramWebhookView.as_view()),
    path("webhooks/instagram/", InstagramWebhookView.as_view()),
]
```
**Tuzoq:** `IntegrationConfigViewSet` (`""` prefiksli, detail route
`^(?P<pk>[^/.]+)/$`) `events`дан **oldin** ro'yxatdan o'tsa, `/events/` so'rovi
`pk="events"` bilan config-lookup sifatida talqin qilinib, **404** qaytaradi.
Shuning uchun **maxsus (aniq) route'lar umumiy/catch-all route'lardan oldin**
ro'yxatdan o'tishi kerak — bu istalgan DRF router konfiguratsiyasida amal
qiladigan umumiy qoida.

---

## 7. Boshqa loyihada qo'llash — checklist

1. `IntegrationConfig(provider, key, value, is_active)` jadvalini ko'chiring —
   har qanday tashqi integratsiya (WhatsApp, Slack, boshqa messenjer) shu bitta
   jadvalga sig'adi, yangi model kerak emas.
2. Har integratsiya uchun **3 ta sof funksiya** yozing: `parse_*` (xom
   payload → umumiy shakl), `send_*` (chiqish), `verify_*` (xavfsizlik). Bular
   Django/DRF'дан mustaqil — testlash oson.
3. Webhook view'lar **doim `AllowAny` + `authentication_classes = []`** —
   o'rniga secret/HMAC tekshiruvi qo'ying, JWT emas.
4. Har kelgan payload'ni **parse qilinmasa ham** log-model (`IntegrationEvent`)
   sifatida saqlang — production debugида bu eng qimmatli narsa.
5. Webhook ичida **hech qachon** sinxron ravishda LLM/uzoq amal chaqirmang —
   darhol 200/202 qaytarib, ishni queue (Celery/RQ)ga o'tkazing.
6. Chiqish tomonida markdown/format tozalashni **bitta markazlashgan
   dispatcher**da qiling, har platformaning yuborish funksiyasida emas.
7. Meta (Instagram/WhatsApp) integratsiyalarida **`is_echo`ни filtrlashni
   unutmang** — aks holda bot o'z-o'ziga javob berib ketadi.
8. URL marshrutlashда **aniq route'larni umumiy (`""`, catch-all)
   route'lardan oldin** ro'yxatdan o'tkazing.
