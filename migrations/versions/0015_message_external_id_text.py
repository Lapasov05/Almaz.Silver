"""message.external_id VARCHAR(128) -> Text (Instagram mid 128 belgidan uzun)

Revision ID: 0015_msg_extid
Revises: 0014_integr
Create Date: 2026-07-27

Sabab: Instagram webhook `mid` ~180 belgi -> VARCHAR(128)ga sig'may INSERT yiqilardi
(xabar saqlanmasdi, 500). Text (limitsiz) qilamiz. Telegram id qisqa edi — ta'sirsiz.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_msg_extid"
down_revision: Union[str, None] = "0014_integr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "message", "external_id",
        existing_type=sa.String(length=128),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "message", "external_id",
        existing_type=sa.Text(),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
