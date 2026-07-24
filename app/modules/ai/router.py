"""ai API qatlami — knowledge base CRUD, prompt ko'rish, agentni qo'lda ishga tushirish.

Ruxsatlar (TZ 13): o'qish `ai:view`, KB/prompt yozish `ai:edit_prompt`, agent `ai:override_ai`.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params
from app.modules.ai.prompts import build_system_prompt
from app.modules.ai.repository import KnowledgeRepository
from app.modules.ai.schemas import (
    AgentRespondOut,
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
    override = override_setting.value if override_setting else None
    return PromptOut(prompt_version=version, system_prompt=build_system_prompt(version, override))


# ==================== Agentni qo'lda ishga tushirish ====================
@router.post(
    "/conversations/{conversation_id}/respond",
    response_model=AgentRespondOut,
    dependencies=[Depends(require_permission("ai:override_ai"))],
)
async def agent_respond(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> AgentRespondOut:
    """AI javobini qo'lda ishga tushirish (debug/override). LLM kaliti kerak."""
    outcome = await AgentService(db).respond(conversation_id)
    return AgentRespondOut(
        status=outcome.status,
        reason=outcome.reason,
        reply=outcome.reply,
        message_id=outcome.message_id,
        used_tools=outcome.used_tools,
        violations=outcome.violations,
        state=outcome.state,
    )
