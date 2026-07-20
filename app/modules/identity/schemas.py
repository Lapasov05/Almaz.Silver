"""identity Pydantic DTO'lari (API kontrakti)."""
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    is_active: bool


class MeResponse(UserOut):
    """Joriy foydalanuvchi + rollari va samarali permission'lari."""

    roles: list[str]
    permissions: list[str]


# ---------- RBAC admin (Faza 6) ----------
class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str | None


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_system: bool


class RoleDetailOut(RoleOut):
    permissions: list[str]


class RolePermissionsSet(BaseModel):
    codes: list[str]  # rolga beriladigan permission kodlari (to'liq almashtiriladi)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role_ids: list[uuid.UUID] | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class UserRolesSet(BaseModel):
    role_ids: list[uuid.UUID]


class UserDetailOut(UserOut):
    roles: list[str]
