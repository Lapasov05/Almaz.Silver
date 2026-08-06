from app.modules.ai.prompts import BASE_SYSTEM_PROMPT


AI_PROMPTS: list[dict] = [
    {
        "key": "ai_system_prompt_v3",
        "purpose": "AI sotuvchining yagona system prompti.",
        "used_in": "app/modules/ai/agent.py",
        "placeholders": "{{PLATFORM}} {{CURRENT_DATE}}",
        "value": BASE_SYSTEM_PROMPT,
    },
    {
        "key": "ai_msg_fallback",
        "purpose": "Function call sikli yakunlanmasa yuboriladigan xabar.",
        "used_in": "app/modules/ai/agent.py",
        "placeholders": "",
        "value": "Kechirasiz, so'rovingizni to'liq bajara olmadim. Operator tez orada bog'lanadi.",
    },
    {
        "key": "ai_msg_order_shipping",
        "purpose": "Buyurtma yo'lga chiqqanda yuboriladigan xabar.",
        "used_in": "app/modules/orders/service.py",
        "placeholders": "",
        "value": "Buyurtmangiz yo'lga chiqdi! 🚚 Uni olganingizdan keyin shu yerda bizga xabar bering.",
    },
    {
        "key": "ai_msg_payment_approved",
        "purpose": "To'lov tasdiqlanganda yuboriladigan xabar.",
        "used_in": "app/modules/payments/service.py",
        "placeholders": "",
        "value": "To'lovingiz tasdiqlandi! ✅ Operatorimiz tez orada siz bilan bog'lanadi.",
    },
    {
        "key": "ai_msg_location_confirmed_head",
        "purpose": "Manzil tasdiqlanganda yuboriladigan xabar boshi.",
        "used_in": "app/modules/delivery/checkout.py",
        "placeholders": "",
        "value": "Manzilingiz qabul qilindi ✅",
    },
    {
        "key": "ai_msg_delivery_tashkent",
        "purpose": "Toshkent yetkazish ma'lumoti.",
        "used_in": "app/modules/delivery/checkout.py",
        "placeholders": "",
        "value": "🚕 Yandex Go orqali yetkazamiz. Narx masofaga qarab belgilanadi va kuryerga to'lanadi.",
    },
    {
        "key": "ai_msg_delivery_bts",
        "purpose": "Viloyat yetkazish ma'lumoti.",
        "used_in": "app/modules/delivery/checkout.py",
        "placeholders": "",
        "value": "📮 BTS orqali 1-2 kunda yetkazamiz. Yetkazish haqi BTS bo'limida to'lanadi.",
    },
    {
        "key": "ai_msg_location_confirmed_card",
        "purpose": "Manzil tasdiqlangach karta va summa xabari.",
        "used_in": "app/modules/delivery/checkout.py",
        "placeholders": "{total} {card} {holder}",
        "value": "💳 To'lov: {total} so'm\nKarta: {card} ({holder})\nTo'lagach chek rasmini yuboring 📸",
    },
    {
        "key": "ai_msg_need_info_before_payment",
        "purpose": "To'lovdan oldin yetishmayotgan mijoz ma'lumoti.",
        "used_in": "app/modules/delivery/checkout.py",
        "placeholders": "{missing}",
        "value": "Buyurtmani yakunlash uchun {missing} yuboring.",
    },
    {
        "key": "ai_msg_location_confirmed_nocard",
        "purpose": "Karta sozlanmagan holatdagi xabar.",
        "used_in": "app/modules/delivery/checkout.py",
        "placeholders": "{total}",
        "value": "To'lov summasi: {total} so'm. Karta ma'lumoti tez orada yuboriladi.",
    },
]

_BY_KEY = {item["key"]: item for item in AI_PROMPTS}


def default_text(key: str) -> str:
    entry = _BY_KEY.get(key)
    return entry["value"] if entry else ""


def prompt_meta(key: str) -> dict | None:
    return _BY_KEY.get(key)


def all_prompt_keys() -> list[str]:
    return [item["key"] for item in AI_PROMPTS]


async def get_ai_text(db, key: str, **fmt) -> str:
    from app.modules.settings.repository import SettingsRepository

    setting = await SettingsRepository(db).get(key)
    text = setting.value if setting is not None and setting.value else default_text(key)
    if not isinstance(text, str):
        text = str(text)
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return text
    return text
