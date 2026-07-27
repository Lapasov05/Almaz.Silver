"""LLM provayder tanlash — OpenAI kaliti DB'dan (IntegrationConfig), env'дан emas."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.ai.llm.base import LLMProvider

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_llm_provider(db: AsyncSession) -> LLMProvider | None:
    """OpenAI api_key DB'да (integration_config openai/api_key) bo'lsa — OpenAI; aks holda None.

    Kalit yagona manba: DB. `LLM_PROVIDER=fake` faqat test/dev uchun (kalitsiz).
    """
    from app.modules.integrations.service import get_config_value

    api_key = await get_config_value(db, "openai", "api_key")
    if api_key:
        base_url = await get_config_value(db, "openai", "base_url")
        from app.modules.ai.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key, base_url=base_url)
    if settings.llm_provider.lower() == "fake":
        from app.modules.ai.llm.fake_provider import FakeProvider

        return FakeProvider()
    logger.info("OpenAI api_key DB'да yo'q — AI jim (integration_config: openai/api_key)")
    return None
