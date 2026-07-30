"""category: available_sizes — kategoriyaga bog'langan o'lchamlar ro'yxati (uzuk razmerlari)

Revision ID: 0023_category_sizes
Revises: 0022_engraving_max_chars
Create Date: 2026-07-31

requires_ring_size=true kategoriyada (masalan Uzuklar) mavjud o'lchamlar ro'yxati saqlanadi
(masalan ["16","16.5","17","17.5","18"]). AI shu o'lchamlarni taklif qiladi; buyurtmada shu ro'yxatdan
tashqari o'lcham berilsa rad etiladi. Bo'sh/NULL — istalgan o'lcham qabul qilinadi (cheklovsiz).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0023_category_sizes"
down_revision: Union[str, None] = "0022_engraving_max_chars"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("category", sa.Column("available_sizes", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("category", "available_sizes")
