"""settings Pydantic DTO'lari."""
from typing import Any

from pydantic import BaseModel, ConfigDict


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any


class SettingUpdate(BaseModel):
    value: Any
