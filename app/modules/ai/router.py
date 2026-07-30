"""ai API qatlami — knowledge base CRUD, prompt ko'rish, agentni qo'lda ishga tushirish.

Ruxsatlar (TZ 13): o'qish `ai:view`, KB/prompt yozish `ai:edit_prompt`, agent `ai:override_ai`.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.exceptions import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.modules.ai.prompt_registry import AI_PROMPTS, get_ai_text, prompt_meta
from app.modules.ai.prompts import build_system_prompt
from app.modules.ai.repository import KnowledgeRepository
from app.modules.ai.schemas import (
    AgentRespondOut,
    AiPromptOut,
    AiPromptUpdate,
    KnowledgeCreate,
    KnowledgeOut,
    KnowledgeType,
    KnowledgeUpdate,
    PromptOut,
)
from app.modules.ai.service import AgentService, KnowledgeService
from app.modules.settings.repository import SettingsRepository

router = APIRouter(prefix="/ai", tags=["ai"])


def get_knowledge_service(db: AsyncSession = Depends(get_db)) -> KnowledgeService:
    return KnowledgeService(KnowledgeRepository(db))


# ==================== Knowledge base (RAG) ====================
@router.post(
    "/knowledge",
    response_model=KnowledgeOut,
    dependencies=[Depends(require_permission("ai:edit_prompt"))],
)
async def create_knowledge(
    payload: KnowledgeCreate, service: KnowledgeService = Depends(get_knowledge_service)
) -> KnowledgeOut:
    kb = await service.create(type_=payload.type.value, title=payload.title, content=payload.content)
    return KnowledgeOut.model_validate(kb)


@router.get(
    "/knowledge",
    response_model=Page[KnowledgeOut],
    dependencies=[Depends(require_permission("ai:view"))],
)
async def list_knowledge(
    type: KnowledgeType | None = None,
    q: str | None = None,
    pp: PageParams = Depends(page_params),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Page[KnowledgeOut]:
    items, total = await service.list_all(type_=type.value if type else None, q=q, pp=pp)
    return Page(items=[KnowledgeOut.model_validate(k) for k in items], total=total, limit=pp.limit, offset=pp.offset)


@router.patch(
    "/knowledge/{kb_id}",
    response_model=KnowledgeOut,
    dependencies=[Depends(require_permission("ai:edit_prompt"))],
)
async def update_knowledge(
    kb_id: uuid.UUID,
    payload: KnowledgeUpdate,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeOut:
    data = {k: (v.value if hasattr(v, "value") else v) for k, v in payload.model_dump(exclude_unset=True).items()}
    return KnowledgeOut.model_validate(await service.update(kb_id, data))


@router.delete(
    "/knowledge/{kb_id}",
    status_code=204,
    dependencies=[Depends(require_permission("ai:edit_prompt"))],
)
async def delete_knowledge(
    kb_id: uuid.UUID, service: KnowledgeService = Depends(get_knowledge_service)
) -> None:
    await service.delete(kb_id)


# ==================== Prompt (TZ 7.2) ====================
@router.get(
    "/prompt",
    response_model=PromptOut,
    dependencies=[Depends(require_permission("ai:view"))],
)
async def get_prompt(db: AsyncSession = Depends(get_db)) -> PromptOut:
    repo = SettingsRepository(db)
    version_setting = await repo.get("prompt_version")
    override_setting = await repo.get("system_prompt_override")
    version = int(version_setting.value) if version_setting else 1
    base = await get_ai_text(db, "ai_system_prompt")  # DB (registr) asosiy prompt
    override = override_setting.value if override_setting else None
    return PromptOut(prompt_version=version, system_prompt=build_system_prompt(version, base, override))


# ==================== AI Promtlar — to'liq boshqaruv (registr + DB) ====================
async def _build_ai_prompt_out(db: AsyncSession, key: str) -> AiPromptOut:
    meta = prompt_meta(key)
    if meta is None:
        raise NotFoundError(f"AI promt topilmadi: {key}")
    setting = await SettingsRepository(db).get(key)
    return AiPromptOut(
        key=key,
        purpose=meta["purpose"],
        used_in=meta["used_in"],
        placeholders=meta.get("placeholders", ""),
        default_value=meta["value"],
        current_value=(setting.value if (setting is not None and setting.value) else meta["value"]),
        is_overridden=setting is not None,
    )


@router.get(
    "/prompts",
    response_model=list[AiPromptOut],
    dependencies=[Depends(require_permission("ai:view"))],
)
async def list_ai_prompts(db: AsyncSession = Depends(get_db)) -> list[AiPromptOut]:
    """Barcha AI promtlar — metama'lumot (maqsad/qayerda/o'rinlar) + standart va joriy qiymat bilan."""
    return [await _build_ai_prompt_out(db, p["key"]) for p in AI_PROMPTS]


@router.get(
    "/prompts/{key}",
    response_model=AiPromptOut,
    dependencies=[Depends(require_permission("ai:view"))],
)
async def get_ai_prompt(key: str, db: AsyncSession = Depends(get_db)) -> AiPromptOut:
    """Bitta AI promt (metama'lumot + joriy qiymat)."""
    return await _build_ai_prompt_out(db, key)


@router.put(
    "/prompts/{key}",
    response_model=AiPromptOut,
    dependencies=[Depends(require_permission("ai:edit_prompt"))],
)
async def update_ai_prompt(
    key: str, payload: AiPromptUpdate, db: AsyncSession = Depends(get_db)
) -> AiPromptOut:
    """AI promt matnini tahrirlaydi (DB'da saqlanadi). Faqat registrdagi kalitlar."""
    if prompt_meta(key) is None:
        raise NotFoundError(f"AI promt topilmadi: {key}")
    await SettingsRepository(db).upsert(key, payload.value)
    await db.commit()
    return await _build_ai_prompt_out(db, key)


@router.post(
    "/prompts/{key}/reset",
    response_model=AiPromptOut,
    dependencies=[Depends(require_permission("ai:edit_prompt"))],
)
async def reset_ai_prompt(key: str, db: AsyncSession = Depends(get_db)) -> AiPromptOut:
    """AI promtni STANDART (registr) qiymatiga qaytaradi — DB'dagi tahrirni o'chiradi."""
    if prompt_meta(key) is None:
        raise NotFoundError(f"AI promt topilmadi: {key}")
    await SettingsRepository(db).delete(key)
    await db.commit()
    return await _build_ai_prompt_out(db, key)


# ==================== Agentni qo'lda ishga tushirish ====================
@router.post(
    "/conversations/{conversation_id}/respond",
    response_model=AgentRespondOut,
    dependencies=[Depends(require_permission("ai:override_ai"))],
)
async def agent_respond(
    conversation_id: uuid.UUID,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
) -> AgentRespondOut:
    """AI javobini qo'lда ishga tushirish (debug/override). LLM kaliti kerak.

    `?force=true` — pauza/handoff/o'chirilган holатда ham AI'ni QAYTA ishga soladi
    (operator qo'lда AI'ga topshiradi). Global kill-switch va yopiq suhbat baribir hurmat.
    """
    outcome = await AgentService(db).respond(conversation_id, force=force)
    return AgentRespondOut(
        status=outcome.status,
        reason=outcome.reason,
        reply=outcome.reply,
        message_id=outcome.message_id,
        used_tools=outcome.used_tools,
        violations=outcome.violations,
        state=outcome.state,
    )
