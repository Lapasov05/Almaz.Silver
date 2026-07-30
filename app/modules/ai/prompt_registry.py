"""AI promt REGISTRI — barcha sun'iy intellekt matnlari BITTA joyda, DB'dan boshqariladi.

Har bir AI matni (system prompt, kontekst shablonlari, tayyor xabarlar) shu yerda ro'yxatga olingan:
  - key         : settings jadvalidagi kalit (DB'da shu nom bilan saqlanadi/tahrirlanadi)
  - purpose     : NIMA UCHUN — maqsadi
  - used_in     : QAYERDA — qaysi fayl/funksiya ishlatadi
  - placeholders: shablondagi {o'rin}lar (agar bo'lsa) — kod .format bilan to'ldiradi
  - value       : STANDART matn (DB'da yo'q bo'lsa shu ishlatiladi — fallback)

Kod DOIM `get_ai_text(db, key, **fmt)` orqali o'qiydi: avval DB (settings), bo'lmasa shu registrdagi
standart. Ya'ni prodda `make ai-prompts-seed` bilan hammasi DB'ga tushadi va u yerdan tahrirlanadi;
kod hech qачон to'g'ridan-to'g'ri matn ushlamaydi (faqat fallback sifatida).
"""
from app.modules.ai.prompts import BASE_SYSTEM_PROMPT

AI_PROMPTS: list[dict] = [
    {
        "key": "ai_system_prompt",
        "purpose": "Asosiy AI sotuvchi system prompt — rol, qat'iy qoidalar (guardrail), uslub, ish oqimi, "
                   "buyurtma ketma-ketligi. AI'ning HAR javobiga qo'yiladi (eng muhim matn).",
        "used_in": "app/modules/ai/agent.py::respond -> build_system_prompt (prompts.py)",
        "placeholders": "",
        "value": BASE_SYSTEM_PROMPT,
    },
    {
        "key": "ai_greeting_text",
        "purpose": "Birinchi salomlashuv — LLM ulanmagan (provider yo'q) rejimda mijozga yuboriladigan "
                   "boshlang'ich xabar. LLM faol bo'lsa ishlatilmaydi.",
        "used_in": "app/modules/ai/agent.py::respond (provider is None tarmog'i)",
        "placeholders": "",
        "value": "Assalomu alaykum! almazsilver zargarlik do'koniga xush kelibsiz. Sizga qanday zargarlik "
                 "buyumi kerak — uzuk, braslet, sepochka yoki zirak?",
    },
    # ---------- Faol buyurtma konteksti (xotira/follow-up) ----------
    {
        "key": "ai_ctx_order",
        "purpose": "Mijozning FAOL buyurtmasi bo'lganda AI har javobga oladigan kontekst shabloni — "
                   "holat, mahsulot, summa, keyingi qadam. Xotira yo'qolishining oldini oladi.",
        "used_in": "app/modules/ai/agent.py::_active_order_context",
        "placeholders": "{order_no} {products} {items_total} {fee} {grand_total} {status} {guide} {hint}",
        "value": "[Faol buyurtma {order_no}: {products}. Summa: {items_total}, yetkazish: {fee}, "
                 "JAMI: {grand_total} so'm. Holat: {status}. Bu mijozning JORIY buyurtmasi — kontekstni "
                 "UNUTMA, boshqa buyurtma yaratma. Keyingi qadam: {guide}{hint}]",
    },
    {
        "key": "ai_ctx_order_guide_pending",
        "purpose": "Faol buyurtma 'pending' (manzil hali tasdiqlanmagan) — AI'ga keyingi qadam ko'rsatmasi.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "Manzil hali TASDIQLANMAGAN. request_location bilan xarita havolasini bering. Mijoz "
                 "'yubordim' desa-yu holat hali pending bo'lsa — xaritada joyni belgilab TASDIQLASH "
                 "tugmasini bosishini muloyim ayting yoki havolani qayta yuboring.",
    },
    {
        "key": "ai_ctx_order_guide_waiting_payment",
        "purpose": "Faol buyurtma 'waiting_payment' (manzil qabul qilingan, to'lov kutilmoqda) — keyingi qadam.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "Manzil qabul qilingan. To'lov kartasini bering (get_payment_card) va chek RASMINI so'rang. "
                 "Mijoz RASM yuborsa — bu to'lov cheki, DARHOL submit_receipt chaqiring.",
    },
    {
        "key": "ai_ctx_order_guide_payment_review",
        "purpose": "Faol buyurtma 'payment_review' (chek yuborilgan, operator tekshirmoqda) — keyingi qadam.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "Chek yuborilgan, operator tekshirmoqda. Mijozga muloyim sabr ayting. Yangi chek (rasm) "
                 "yuborsa submit_receipt. Suhbatni tugatma, savoliga javob ber.",
    },
    {
        "key": "ai_ctx_order_guide_default",
        "purpose": "Faol buyurtma boshqa holatда — umumiy keyingi qadam ko'rsatmasi.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide fallback)",
        "placeholders": "",
        "value": "Buyurtmani yakunlashda davom et.",
    },
    {
        "key": "ai_ctx_order_receipt_hint",
        "purpose": "Mijoz to'lov bosqichida RASM yuborganда — bu chek ekanini AI'ga eslatuvchi qo'shimcha.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (hint)",
        "placeholders": "",
        "value": " MIJOZ HOZIR RASM YUBORDI — bu to'lov cheki, DARHOL submit_receipt chaqiring.",
    },
    # ---------- Instagram konteksti (post/reel/story grounding) ----------
    {
        "key": "ai_ctx_instagram_found",
        "purpose": "Mijoz IG post/reel/story yuborib, mahsulot bazadan TOPILGANда — AI'ga grounding konteksti.",
        "used_in": "app/modules/ai/agent.py::_instagram_context",
        "placeholders": "{name} {price} {avail} {tip}",
        "value": "[Instagram konteksti: mijoz '{name}' mahsulotini ko'rdi. Narx: {price}. Zaxira: {avail}. {tip}]",
    },
    {
        "key": "ai_ctx_instagram_tip_instock",
        "purpose": "IG mahsulot ZAXIRADA bor — AI'ga ko'rsatma (savdoni davom ettir).",
        "used_in": "app/modules/ai/agent.py::_instagram_context (tip)",
        "placeholders": "",
        "value": "Shu mahsulot bo'yicha savdoni davom ettir (o'lcham/zaxira/narx).",
    },
    {
        "key": "ai_ctx_instagram_tip_outstock",
        "purpose": "IG mahsulot ZAXIRADA yo'q — AI'ga ko'rsatma (muloyim ayt + o'xshash taklif).",
        "used_in": "app/modules/ai/agent.py::_instagram_context (tip)",
        "placeholders": "",
        "value": "Zaxirada yo'q - mijozga muloyim ayt va o'xshash mahsulot taklif qil (recommend).",
    },
    {
        "key": "ai_ctx_instagram_not_found",
        "purpose": "Mijoz IG post/reel/story yubordi, lekin mahsulot bazaga ulanmagan/topilmadi — AI odamdek uzr aytadi.",
        "used_in": "app/modules/ai/agent.py::_instagram_context",
        "placeholders": "",
        "value": "[Instagram: mijoz post/reel/story (rasm yoki video) yubordi, lekin u bazaga ulanmagan — "
                 "mahsulot topilmadi. Mijozga ODAMDEK, muloyim uzr ayting (masalan: 'Kechirasiz, bu "
                 "videodagi mahsulotni topolmadim') va mahsulot nomini yoki suratini so'rang. Bir xil "
                 "jumlani takrorlamang, tabiiy yozing.]",
    },
    # ---------- Tayyor (fixed) xabarlar ----------
    {
        "key": "ai_msg_fallback",
        "purpose": "AI tool-sikli tugab, so'rovni bajara olmaganда mijozga yuboriladigan xabar (operatorga o'tkaziladi).",
        "used_in": "app/modules/ai/agent.py::respond (sikl tugagani)",
        "placeholders": "",
        "value": "Kechirasiz, so'rovingizni to'liq bajara olmadim. Operator tez orada bog'lanadi.",
    },
    {
        "key": "ai_msg_location_confirmed_head",
        "purpose": "Mijoz manzilni web xarita orqali tasdiqlagach AVTOMATIK yuboriladigan xabarning boshi "
                   "(manzil qabul qilindi + summa). Mijoz 'yubordim' deyishini kutmaydi.",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup",
        "placeholders": "{fee} {total}",
        "value": "Manzilingiz qabul qilindi ✅\nYetkazish: {fee} so'm. Jami to'lov: {total} so'm.",
    },
    {
        "key": "ai_msg_location_confirmed_card",
        "purpose": "Manzil tasdiqlangach — to'lov kartasi + chek so'rovi (karta mavjud bo'lsa).",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup",
        "placeholders": "{card} {holder}",
        "value": "To'lov uchun karta: {card} ({holder}).\nTo'lovni amalga oshirgach, chek RASMINI shu yerga yuboring.",
    },
    {
        "key": "ai_msg_location_confirmed_nocard",
        "purpose": "Manzil tasdiqlangach — karta sozlanmagan bo'lsa yuboriladigan xabar.",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup",
        "placeholders": "",
        "value": "To'lov kartasi ma'lumoti tez orada yuboriladi.",
    },
]

_BY_KEY = {p["key"]: p for p in AI_PROMPTS}


def default_text(key: str) -> str:
    """Registrdagi standart matn (kod fallback). Kalit yo'q bo'lsa bo'sh satr."""
    entry = _BY_KEY.get(key)
    return entry["value"] if entry else ""


async def get_ai_text(db, key: str, **fmt) -> str:
    """AI matnini oladi: avval DB (settings), bo'lmasa registr standarti. `fmt` berilsa .format bilan to'ldiradi.

    Bitta manba: hamma AI matni shu funksiya orqali o'qiladi — koddan emas, DB'dan boshqariladi.
    """
    from app.modules.settings.repository import SettingsRepository

    setting = await SettingsRepository(db).get(key)
    text = setting.value if (setting is not None and setting.value) else default_text(key)
    if not isinstance(text, str):
        text = str(text)
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            pass  # tahrirlangan matnda o'rin mos kelmasa — xom matnni beramiz (buzilmaydi)
    return text
