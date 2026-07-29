"""bts_branch (yetkazish punktlari) + customer_location + delivery lokatsiya turi (TZ 11)

Revision ID: 0020_bts_location
Revises: 0019_delivery_extra
Create Date: 2026-07-29

Lokatsiya oqimi: frontend map linkidan lat/lng keladi. Toshkent ichida → type Toshkent (50k);
tashqarida → type BTS (30k) + eng yaqin bts_branch. Mijoz lokatsiyasi customer_location'da (id bilan).
BTS filiallari bot_branches.json'dan seed qilinadi (dinamik — keyin qo'shsa bo'ladi).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_bts_location"
down_revision: Union[str, None] = "0019_delivery_extra"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- bts_branch ---
    op.create_table(
        "bts_branch",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("ext_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("region", sa.String(120), nullable=True),
        sa.Column("district", sa.String(120), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("landmark", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("work_hours", sa.String(255), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bts_branch_ext_id", "bts_branch", ["ext_id"], unique=True)

    # --- customer_location ---
    op.create_table(
        "customer_location",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("customer_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customer.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("location_type", sa.String(20), nullable=False),
        sa.Column("bts_branch_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bts_branch.id", ondelete="SET NULL"), nullable=True),
        sa.Column("address_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_location_customer_id", "customer_location", ["customer_id"])

    # --- delivery: lokatsiya turi + biriktirilgan yozuvlar ---
    op.add_column("delivery", sa.Column("location_type", sa.String(20), nullable=True))
    op.add_column("delivery", sa.Column("customer_location_id", sa.dialects.postgresql.UUID(as_uuid=True),
                                        nullable=True))
    op.add_column("delivery", sa.Column("bts_branch_id", sa.dialects.postgresql.UUID(as_uuid=True),
                                        nullable=True))
    op.create_foreign_key("fk_delivery_customer_location", "delivery", "customer_location",
                          ["customer_location_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_delivery_bts_branch", "delivery", "bts_branch",
                          ["bts_branch_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_delivery_bts_branch", "delivery", type_="foreignkey")
    op.drop_constraint("fk_delivery_customer_location", "delivery", type_="foreignkey")
    op.drop_column("delivery", "bts_branch_id")
    op.drop_column("delivery", "customer_location_id")
    op.drop_column("delivery", "location_type")
    op.drop_index("ix_customer_location_customer_id", table_name="customer_location")
    op.drop_table("customer_location")
    op.drop_index("ix_bts_branch_ext_id", table_name="bts_branch")
    op.drop_table("bts_branch")
