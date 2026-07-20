"""Boshlang'ich biznes sozlamalari (TZ 14-bo'lim).

Bu qiymatlar seed vaqtida `setting` jadvaliga yoziladi (faqat mavjud bo'lmasa).
Barcha biznes logikasi shu sozlamalardan boshqariladi.
"""
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    # --- Feature flag'lar ---
    "payment_required": True,          # TZ 12: faqat prepaid
    "reject_reason_required": False,   # TZ 12: rad sababi majburiymi
    "delivery_enabled": True,
    "ai_enabled": True,                # TZ 14: AS to'liq avtonom sotuvchi
    "instagram_enabled": True,
    "telegram_enabled": True,

    # --- Ish rejimi ---
    "working_hours": {"start": "09:00", "end": "21:00", "timezone": "Asia/Tashkent"},
    "auto_reply": True,
    "operator_timeout": 300,           # operator javob kutish (soniya)
    "ai_pause_minutes": 15,            # TZ 9: operator yozgach AI pauzasi (daqiqa)

    # --- AI / LLM (TZ 7.2) ---
    "ai_temperature": 0.7,
    "llm_model": "gpt-4o",
    "prompt_version": 1,

    # --- Yetkazish (TZ 11) — zona bo'yicha fixed narx ---
    "delivery_fee_tashkent": 50000,
    "delivery_fee_region": 30000,
    "yandex_enabled": False,           # TZ 11: Yandex API integratsiyasi yo'q
    "bts_enabled": True,

    # --- Bonus va to'lov (TZ 2/12/14) ---
    "bonus_items": ["upakovka", "brend paket"],  # barcha buyurtmalarga bir xil
    # Eslatma (Faza 5): kartalar endi `payment_card` jadvalida. Quyidagilar eskirgan (legacy).
    "payment_cards": [],
    "primary_card": None,
    # To'lov chekini tasdiqlash (TZ 12): owner/manager Telegram chat + javobgar CRM user
    "payment_review_telegram_chat_id": None,
    "payment_reviewer_user_id": None,
}
