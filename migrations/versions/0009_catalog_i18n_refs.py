"""catalog: ko'p tilli (uz/ru), reference jadvallar (gender/material/stone),
narx (price + discount_price), og'irlik kalkulyatori (weight_grams / gram_price)

Revision ID: 0009_catalog_i18n
Revises: 0008_engraving
Create Date: 2026-07-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_catalog_i18n"
down_revision: Union[str, None] = "0008_engraving"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)

_SEARCH_EXPR = (
    "to_tsvector('simple', "
    "coalesce(name_uz, '') || ' ' || coalesce(name_ru, '') || ' ' || "
    "coalesce(description_uz, '') || ' ' || coalesce(description_ru, '') || ' ' || "
    "coalesce(ai_keywords::text, ''))"
)


def _reference_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name_uz", sa.String(150), nullable=False),
        sa.Column("name_ru", sa.String(150), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    # ── 1) Reference lug'atlar + boshlang'ich qiymatlar ──
    for t in ("gender", "material", "stone"):
        _reference_table(t)
    op.execute(
        "INSERT INTO gender (name_uz, name_ru, sort_order) VALUES "
        "('Erkak','Мужской',1),('Ayol','Женский',2),('Uniseks','Унисекс',3)"
    )
    op.execute("INSERT INTO material (name_uz, name_ru) VALUES ('Kumush 925 + rodiy','Серебро 925 + родий')")
    op.execute("INSERT INTO stone (name_uz, name_ru) VALUES ('Serkon','Серкон (фианит)')")

    # ── 2) Category: ko'p tilli + gramm narxi ──
    op.add_column("category", sa.Column("name_uz", sa.String(150), nullable=True))
    op.add_column("category", sa.Column("name_ru", sa.String(150), nullable=True))
    op.add_column("category", sa.Column("gram_price", sa.Numeric(12, 2), nullable=True))
    op.execute("UPDATE category SET name_uz = name")
    op.alter_column("category", "name_uz", nullable=False)
    op.drop_column("category", "name")

    # ── 3) Product: generated ustun bog'liqligini avval olib tashlaymiz ──
    op.drop_index("ix_product_search_vector", table_name="product")
    op.drop_column("product", "search_vector")

    # 3a) ko'p tilli ustunlar
    op.add_column("product", sa.Column("name_uz", sa.String(255), nullable=True))
    op.add_column("product", sa.Column("name_ru", sa.String(255), nullable=True))
    op.add_column("product", sa.Column("description_uz", sa.Text(), nullable=True))
    op.add_column("product", sa.Column("description_ru", sa.Text(), nullable=True))
    op.execute("UPDATE product SET name_uz = name, description_uz = description")
    op.alter_column("product", "name_uz", nullable=False)
    op.drop_column("product", "name")
    op.drop_column("product", "description")

    # 3b) reference FK'lar + eski matn qiymatlarini ko'chirish
    op.add_column("product", sa.Column("gender_id", _UUID, nullable=True))
    op.add_column("product", sa.Column("material_id", _UUID, nullable=True))
    op.add_column("product", sa.Column("stone_id", _UUID, nullable=True))
    op.execute(
        "UPDATE product p SET gender_id = g.id FROM gender g "
        "WHERE lower(g.name_uz) = lower(p.gender)"
    )
    op.execute("UPDATE product SET material_id = (SELECT id FROM material ORDER BY created_at LIMIT 1)")
    op.execute("UPDATE product SET stone_id = (SELECT id FROM stone ORDER BY created_at LIMIT 1)")
    op.create_foreign_key("fk_product_gender", "product", "gender", ["gender_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_product_material", "product", "material", ["material_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_product_stone", "product", "stone", ["stone_id"], ["id"], ondelete="SET NULL")
    op.drop_column("product", "gender")
    op.drop_column("product", "material")
    op.drop_column("product", "stone")

    # 3c) narx: price = asosiy (chizilgan), discount_price = mijoz to'laydigan
    op.add_column("product", sa.Column("discount_price", sa.Numeric(12, 2), nullable=True))
    op.execute(
        "UPDATE product SET discount_price = price, price = compare_at_price "
        "WHERE compare_at_price IS NOT NULL AND compare_at_price > price"
    )
    op.drop_column("product", "compare_at_price")

    # 3d) og'irlik
    op.add_column("product", sa.Column("weight_grams", sa.Numeric(8, 3), nullable=True))

    # 3e) search_vector'ni yangi ustunlar bilan qayta yaratamiz
    op.add_column(
        "product",
        sa.Column("search_vector", postgresql.TSVECTOR(), sa.Computed(_SEARCH_EXPR, persisted=True), nullable=True),
    )
    op.create_index("ix_product_search_vector", "product", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_product_search_vector", table_name="product")
    op.drop_column("product", "search_vector")
    op.drop_column("product", "weight_grams")
    op.add_column("product", sa.Column("compare_at_price", sa.Numeric(12, 2), nullable=True))
    op.execute("UPDATE product SET compare_at_price = price, price = discount_price WHERE discount_price IS NOT NULL")
    op.drop_column("product", "discount_price")
    op.add_column("product", sa.Column("gender", sa.String(20), server_default="uniseks", nullable=False))
    op.add_column("product", sa.Column("material", sa.String(100), server_default="Kumush 925 + rodiy", nullable=False))
    op.add_column("product", sa.Column("stone", sa.String(100), server_default="serkon", nullable=False))
    op.execute("UPDATE product p SET gender = lower(g.name_uz) FROM gender g WHERE g.id = p.gender_id")
    for c in ("gender_id", "material_id", "stone_id"):
        op.drop_column("product", c)
    op.add_column("product", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("product", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE product SET name = name_uz, description = description_uz")
    op.alter_column("product", "name", nullable=False)
    for c in ("name_uz", "name_ru", "description_uz", "description_ru"):
        op.drop_column("product", c)
    op.add_column(
        "product",
        sa.Column("search_vector", postgresql.TSVECTOR(),
                  sa.Computed("to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(ai_keywords::text,''))", persisted=True),
                  nullable=True),
    )
    op.create_index("ix_product_search_vector", "product", ["search_vector"], postgresql_using="gin")
    op.add_column("category", sa.Column("name", sa.String(150), nullable=True))
    op.execute("UPDATE category SET name = name_uz")
    op.alter_column("category", "name", nullable=False)
    for c in ("name_uz", "name_ru", "gram_price"):
        op.drop_column("category", c)
    for t in ("stone", "material", "gender"):
        op.drop_table(t)
