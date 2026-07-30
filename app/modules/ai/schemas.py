"""ai Pydantic DTO'lari."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ai.models import KnowledgeType


class KnowledgeCreate(BaseModel):
    type: KnowledgeType
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class KnowledgeUpdate(BaseModel):
    type: KnowledgeType | None = None
    title: str | None = Field(default=None, max_length=255)
    content: str | None = None


class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: KnowledgeType
    title: str
    content: str
    created_at: datetime


class PromptOut(BaseModel):
    prompt_version: int
    system_prompt: str


class AiPromptOut(BaseModel):
    """Bitta AI promt — metama'lumot (maqsad/qayerda/o'rinlar) + standart va joriy qiymat."""
    key: str
    purpose: str
    used_in: str
    placeholders: str
    default_value: str      # registrdagi standart (kod fallback)
    current_value: str      # hozir amalda bo'lgan (DB'da bo'lsa o'sha, aks holda default)
    is_overridden: bool     # DB'da tahrirlanganmi (True = default emas)


class AiPromptUpdate(BaseModel):
    value: str = Field(min_length=1)


class AgentRespondOut(BaseModel):
    status: str
    reason: str | None = None
    reply: str | None = None
    message_id: uuid.UUID | None = None
    used_tools: list[str] = []
    violations: list[str] = []
    state: str | None = None
