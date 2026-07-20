"""LLM provayder tanlash (settings/env asosida)."""
import logging

from app.core.config import get_settings
from app.modules.ai.llm.base import LLMProvider

logger = logging.getLogger(__name__)
settings = get_settings()


def get_llm_provider() -> LLMProvider | None:
    """Sozlamaga qarab provayder qaytaradi; mos kelmasa None (AI jim turadi)."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("LLM_PROVIDER=openai, ammo OPENAI_API_KEY bo'sh — AI jim turadi")
            return None
        from app.modules.ai.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if provider == "fake":
        from app.modules.ai.llm.fake_provider import FakeProvider

        return FakeProvider()
    return None
