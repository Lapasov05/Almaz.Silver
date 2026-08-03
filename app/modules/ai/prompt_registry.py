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
        "value": "Manzil hali TASDIQLANMAGAN. Tartib: (1) AVVAL request_location bilan xarita havolasini ber; "
                 "(2) so'ng 'lokatsiyani topishда muammo bo'lmayaptimi?' deб so'ra. (3) Mijoz muammo borligini "
                 "aytsa YOKI 'yubordim/belgiladim' desa-yu holat hali pending bo'lsa (link ishlamagan) — "
                 "manzilini MATN bilan yozishini so'ra va set_delivery_address bilan qabul qil. (4) Mijoz o'zi "
                 "manzilni MATN bilan yozsa — link kutmay set_delivery_address chaqir. Bir manzilni takror "
                 "so'ramа, matn bilan qabul qil.",
    },
    {
        "key": "ai_ctx_order_guide_waiting_payment",
        "purpose": "Faol buyurtma 'waiting_payment' (manzil qabul qilingan, to'lov kutilmoqda) — keyingi qadam.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "Manzil qabul qilingan. AVVAL mijozning ISM-FAMILIYA va TELEFON raqami bor-yo'qligini tekshir "
                 "— biror biri yo'q bo'lsa AVVAL o'shani so'ra (save_customer_name), to'lov kartasini BERMA. "
                 "Ikkalasi ham bo'lsa: kartani ber (get_payment_card) va chek RASMINI so'ra. Mijoz RASM "
                 "yuborsa — bu to'lov cheki, DARHOL submit_receipt chaqir.",
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
        "key": "ai_ctx_order_guide_confirmed",
        "purpose": "Buyurtma 'confirmed' (to'lov tasdiqlangan, operator tayyorlamoqda) — AI mijozга tinchlik beradi.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "To'lov tasdiqlangan, buyurtma tayyorlanmoqda. Operator tez orada aloqaga chiqadi. Mijoz "
                 "savol bersa javob ber; boshqa mahsulot so'rasa yordam ber.",
    },
    {
        "key": "ai_ctx_order_guide_shipping",
        "purpose": "Buyurtma 'shipping' (yo'lda) — mijoz 'oldim' desa complete_order; shikoyat -> raqam; savol -> javob.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "Buyurtma yo'lda. Mijoz buyumni OLGANINI aytsa ('oldim', 'yetib keldi', 'rahmat') — "
                 "complete_order chaqir (buyurtma yakunlanadi) va minnatdorchilik bildir. Mijoz OLMAGANINI/"
                 "kelmaganini aytsa ('olmadim', 'kelmadi', 'hali yo'q') — BAHSLASHMA, 'yetkazildi' DEMA: "
                 "muloyim uzr ayt, operator raqamini ber va handoff_to_operator chaqir. Boshqa savol/mahsulot — yordam ber.",
    },
    {
        "key": "ai_ctx_order_guide_delivered",
        "purpose": "Buyurtma 'delivered' — mijoz olganini tasdiqlasa complete_order.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide)",
        "placeholders": "",
        "value": "Buyurtma yetkazilgan. Mijoz olganini tasdiqlasa complete_order chaqir. Mijoz OLMAGANINI "
                 "aytsa ('olmadim', 'kelmadi') — BAHSLASHMA, 'yetkazildi' deб turib olma: muloyim uzr ayt, "
                 "operator raqamini ber va handoff_to_operator chaqir (operator tekshiradi). Shikoyat -> raqam.",
    },
    {
        "key": "ai_ctx_order_guide_default",
        "purpose": "Faol buyurtma boshqa holatда — umumiy keyingi qadam ko'rsatmasi.",
        "used_in": "app/modules/ai/agent.py::_active_order_context (guide fallback)",
        "placeholders": "",
        "value": "Buyurtma jarayonda. Mijoz savoliga javob ber; boshqa mahsulot so'rasa yordam ber.",
    },
    {
        "key": "ai_msg_order_shipping",
        "purpose": "Buyurtma 'yo'lda' (shipping) statusiga o'tganda mijozga AVTOMATIK yuboriladigan xabar.",
        "used_in": "app/modules/orders/service.py::set_status (shipping)",
        "placeholders": "",
        "value": "Buyurtmangiz yo'lga chiqdi! 🚚 Uni olganingizdan keyin, iltimos, shu yerda bizga xabar bering.",
    },
    {
        "key": "ai_msg_payment_approved",
        "purpose": "To'lov tasdiqlanganda mijozga yuboriladigan xabar (operator aloqaga chiqadi).",
        "used_in": "app/modules/payments/service.py::approve",
        "placeholders": "",
        "value": "To'lovingiz tasdiqlandi! ✅ Operatorimiz siz bilan tez orada buyurtmangiz yuzasidan "
                 "aloqaga chiqadi.",
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
        "key": "ai_msg_test_mode_notice",
        "purpose": "AI TEST rejimida (settings.ai_test_mode=true) — AI suhbatga BIRINCHI qo'shilганда, "
                   "mijozда davom etayotgan buyurtma YO'Q bo'lsa: yumshoq ogohlantirish (test yordamchi, "
                   "buyurtmani shu yerdan davom ettira oladi).",
        "used_in": "app/modules/ai/agent.py::respond (test_join, buyurtmasiz)",
        "placeholders": "",
        "value": ("ℹ️ Salom! Men almazsilver'ning avtomatik yordamchisiman va hozircha test rejimida "
                  "ishlayapman. Buyurtmangizni shu yerdan bemalol davom ettiraveraman 😊"),
    },
    {
        "key": "ai_msg_test_mode_notice_has_order",
        "purpose": "TEST rejimi — AI suhbatga qo'shilganда mijozда DAVOM ETAYOTGAN buyurtma bo'lsa: AI o'zi "
                   "davom etmaydi (buyurtmani hijack qilmaydi), admin/operator bog'lanishini yumshoq aytadi.",
        "used_in": "app/modules/ai/agent.py::respond (test_join + mavjud buyurtma)",
        "placeholders": "{order_no}",
        "value": ("ℹ️ Salom! Men almazsilver'ning avtomatik yordamchisiman (test rejimi). Sizda avval "
                  "boshlangan buyurtma (№ {order_no}) bor ekan — uni operatorimiz shaxsan tekshirib, tez "
                  "orada siz bilan bog'lanib, batafsil xabar beradi. 😊"),
    },
    {
        "key": "ai_msg_location_confirmed_head",
        "purpose": "Manzil web xarita orqali tasdiqlangach AVTOMATIK yuboriladigan xabarning boshi.",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup",
        "placeholders": "",
        "value": "Manzilingiz qabul qilindi ✅",
    },
    {
        "key": "ai_msg_delivery_tashkent",
        "purpose": "Toshkent (Yandex) zonasi uchun yetkazish MA'LUMOTI. Dostavka pulini mijoz KURYERGA "
                   "o'zi to'laydi (buyurtma summasiga qo'shilmaydi).",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup (Toshkent) + prompt (7-qadam)",
        "placeholders": "",
        "value": ("🚕 Yandex Go orqali shahar bo'ylab yetkazib beramiz\n"
                  "⏱ 1 soat ichida yetib boradi\n"
                  "💰 Dostavka narxi masofaga qarab — uni kuryerga o'zingiz to'laysiz\n"
                  "📦 Zakazlar har kuni, istalgan vaqtda qabul qilinadi\n"
                  "⚡ To'lov qilingan zahoti Yandex orqali yuboramiz ✅"),
    },
    {
        "key": "ai_msg_delivery_bts",
        "purpose": "Viloyat (BTS pochta) zonasi uchun yetkazish MA'LUMOTI. Dostavka narxini mijoz BTS "
                   "bazasida to'laydi (buyurtma summasiga qo'shilmaydi).",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup (viloyat) + prompt (7-qadam)",
        "placeholders": "",
        "value": ("📮 BTS pochta orqali chiqarib beramiz — 1-2 kun ichida yetib boradi\n"
                  "💰 Dostavka narxi 30 000 so'm atrofida — uni BTS pochta bazasida to'laysiz\n"
                  "🚚 BTS har kuni reys: pochtalarni 18:00 gacha qabul qiladi\n"
                  "⏰ Bizga 17:00 gacha to'lov qilsangiz, zakazingiz bugungi reys bilan chiqib ketadi ✅"),
    },
    {
        "key": "ai_msg_location_confirmed_card",
        "purpose": "Manzil tasdiqlangach — bizga to'lov (mahsulotlar summasi) + karta + chek so'rovi.",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup",
        "placeholders": "{total} {card} {holder}",
        "value": ("💳 Bizga esa to'lovni oldindan karta orqali qilasiz 😊\n"
                  "To'lov (mahsulotlar): {total} so'm\n"
                  "Karta: {card} ({holder})\n"
                  "To'lagach chek RASMINI shu yerga yuboring 📸"),
    },
    {
        "key": "ai_msg_need_info_before_payment",
        "purpose": "Manzil tasdiqlangач, lekin ism yoki telefon yetishmasa — karta O'RNIGA yetishgan "
                   "ma'lumotni so'raydi (to'lovga o'tishdan oldin majburiy).",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup (gate)",
        "placeholders": "{missing}",
        "value": "Buyurtmani yakunlash uchun {missing} yuboring — so'ng to'lov kartasini beraman 😊",
    },
    {
        "key": "ai_msg_location_confirmed_nocard",
        "purpose": "Manzil tasdiqlangach — karta sozlanmagan bo'lsa yuboriladigan xabar.",
        "used_in": "app/modules/delivery/checkout.py::_send_payment_followup",
        "placeholders": "{total}",
        "value": "💳 Bizga to'lov (mahsulotlar): {total} so'm — karta ma'lumoti tez orada yuboriladi.",
    },
]

_BY_KEY = {p["key"]: p for p in AI_PROMPTS}


def default_text(key: str) -> str:
    """Registrdagi standart matn (kod fallback). Kalit yo'q bo'lsa bo'sh satr."""
    entry = _BY_KEY.get(key)
    return entry["value"] if entry else ""


def prompt_meta(key: str) -> dict | None:
    """Bitta promt metama'lumoti (key/purpose/used_in/placeholders/value). Yo'q bo'lsa None."""
    return _BY_KEY.get(key)


def all_prompt_keys() -> list[str]:
    """Registrdagi barcha promt kalitlari (tartib bo'yicha)."""
    return [p["key"] for p in AI_PROMPTS]


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
