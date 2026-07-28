"""delivery: phone + landmark (orientir) + apartment (qavat/kvartira/domofon)

Revision ID: 0019_delivery_extra
Revises: 0018_ig_media
Create Date: 2026-07-28

Yandex xarita checkout: mijoz lat/lng + telefon + orientir + qavat/kvartira yuboradi.
Zona (Toshkent/viloyat) lat/lng'dan avtomatik aniqlanadi (kod tomonda).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_delivery_extra"
down_revision: Union[str, None] = "0018_ig_media"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("delivery", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column("delivery", sa.Column("landmark", sa.String(255), nullable=True))
    op.add_column("delivery", sa.Column("apartment", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("delivery", "apartment")
    op.drop_column("delivery", "landmark")
    op.drop_column("delivery", "phone")
