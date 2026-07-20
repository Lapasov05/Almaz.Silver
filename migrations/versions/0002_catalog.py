"""phase1 catalog — category, product, variant, product_media + qidiruv indekslari

Revision ID: 0002_catalog
Revises: 0001_phase0
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002_catalog"
down_revision: Union[str, None] = "0001_phase0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)

# Product.search_vector generatsiya ifodasi (models.py bilan bir xil)
_SEARCH_EXPR = (
    "to_tsvector('simple', "
    "coalesce(name, '') || ' ' || "
    "coalesce(description, '') || ' ' || "
    "coalesce(ai_keywords::text, ''))"
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _id_column() -> sa.Column:
    return sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True)


def upgrade() -> None:
    # --- category (self-FK: parent_id) ---
    op.create_table(
        "category",
        _id_column(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(150), nullable=False),
        sa.Column("parent_id", _UUID, nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["parent_id"], ["category.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug", name="uq_category_slug"),
    )
    op.create_index("ix_category_slug", "category", ["slug"])

    # --- product (generated search_vector + GIN) ---
    op.create_table(
        "product",
        _id_column(),
        sa.Column("category_id", _UUID, nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "gender",
            sa.Enum("erkak", "ayol", "uniseks", name="gender", native_enum=False, length=20),
            server_default="uniseks",
            nullable=False,
        ),
        sa.Column("material", sa.String(100), server_default="Kumush 925 + rodiy", nullable=False),
        sa.Column("stone", sa.String(100), server_default="serkon", nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("compare_at_price", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="product_status", native_enum=False, length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ai_keywords", postgresql.JSONB(), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(_SEARCH_EXPR, persisted=True),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_product_category_id", "product", ["category_id"])
    op.create_index("ix_product_status", "product", ["status"])
    # TZ 6.3: to'liq matn qidiruvi uchun GIN indeks
    op.create_index(
        "ix_product_search_vector", "product", ["search_vector"], postgresql_using="gin"
    )

    # --- variant (zaxira variant ichida) ---
    op.create_table(
        "variant",
        _id_column(),
        sa.Column("product_id", _UUID, nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("barcode", sa.String(64), nullable=True),
        sa.Column(
            "fulfillment_type",
            sa.Enum("stocked", "made_to_order", "unique", name="fulfillment_type", native_enum=False, length=20),
            server_default="stocked",
            nullable=False,
        ),
        sa.Column("stock_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("sku", name="uq_variant_sku"),
        sa.UniqueConstraint("barcode", name="uq_variant_barcode"),
    )
    op.create_index("ix_variant_product_id", "variant", ["product_id"])
    op.create_index("ix_variant_sku", "variant", ["sku"])

    # --- product_media (IG shortcode + pgvector embedding) ---
    op.create_table(
        "product_media",
        _id_column(),
        sa.Column("product_id", _UUID, nullable=False),
        sa.Column(
            "channel",
            sa.Enum("instagram", "telegram", name="media_channel", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("external_media_id", sa.String(255), nullable=True),
        sa.Column("shortcode", sa.String(100), nullable=True),
        sa.Column("permalink", sa.String(500), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("shortcode", name="uq_product_media_shortcode"),
    )
    op.create_index("ix_product_media_product_id", "product_media", ["product_id"])
    # TZ 6.3: pgvector hnsw indeks (kosinus masofasi)
    op.create_index(
        "ix_product_media_embedding",
        "product_media",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("product_media")
    op.drop_table("variant")
    op.drop_table("product")
    op.drop_table("category")
