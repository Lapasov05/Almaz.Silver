"""phase0 foundation — pgvector, RBAC (user/role/permission/...) va setting jadvallari

Revision ID: 0001_phase0
Revises:
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Umumiy ustunlar (TZ 6.1): UUID PK + created_at/updated_at
_UUID = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _id_column() -> sa.Column:
    return sa.Column(
        "id",
        _UUID,
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )


def upgrade() -> None:
    # pgvector — semantik qidiruv/rasm fallback uchun (TZ 3/6.3). Keyingi fazalar ishlatadi.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- user ---
    op.create_table(
        "user",
        _id_column(),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )
    op.create_index("ix_user_email", "user", ["email"])

    # --- role ---
    op.create_table(
        "role",
        _id_column(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_role_name"),
    )

    # --- permission ---
    op.create_table(
        "permission",
        _id_column(),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_permission_code"),
    )
    op.create_index("ix_permission_code", "permission", ["code"])

    # --- role_permission (M:N) ---
    op.create_table(
        "role_permission",
        sa.Column("role_id", _UUID, nullable=False),
        sa.Column("permission_id", _UUID, nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # --- user_role (M:N + scope) ---
    op.create_table(
        "user_role",
        sa.Column("user_id", _UUID, nullable=False),
        sa.Column("role_id", _UUID, nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # --- setting (key-value) ---
    op.create_table(
        "setting",
        _id_column(),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("key", name="uq_setting_key"),
    )
    op.create_index("ix_setting_key", "setting", ["key"])


def downgrade() -> None:
    op.drop_table("setting")
    op.drop_table("user_role")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
    op.drop_table("user")
    # pgvector extension'ni saqlaymiz (boshqa obyektlar ishlatishi mumkin)
