"""integrations Pydantic DTO'lari."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IntegrationConfigCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=32)  # telegram | instagram | openai
    key: str = Field(min_length=1, max_length=120)      # bot_token, access_token, ...
    value: str | None = None
    is_active: bool = True


class IntegrationConfigUpdate(BaseModel):
    value: str | None = None
    is_active: bool | None = None


class IntegrationConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    key: str
    value: str | None      # sezgir — faqat manage_integrations ko'radi
    is_active: bool
    updated_at: datetime


class IntegrationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    direction: str
    raw: dict | None
    status: str
    note: str | None
    created_at: datetime


class WebhookSetupRequest(BaseModel):
    url: str = Field(min_length=1)  # ochiq https webhook manzili
