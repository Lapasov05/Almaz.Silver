"""Demo Instagram media — mahsulotlarga demo post + story link biriktiradi.

Har mahsulotga 1 post + 1 story (bitta mahsulotga ikkalasi ham). IDEMPOTENT: IG media
bo'lgan mahsulotlar o'tkazib yuboriladi. Talab: avval `python -m app.demo_seed`.

Ishga tushirish:  docker compose exec api python -m app.demo_instagram
"""
import asyncio

import app.core.models_registry  # noqa: F401
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.modules.catalog.models import Product, ProductMedia
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import InstagramMediaCreate
from app.modules.catalog.service import CatalogService

MAX_PRODUCTS = 8


async def main() -> None:
    async with SessionLocal() as db:
        prods = (await db.execute(
            select(Product)
            .where(Product.is_combo.is_(False), Product.deleted_at.is_(None), Product.status == "active")
            .order_by(Product.created_at)
            .limit(MAX_PRODUCTS)
        )).scalars().all()
        if not prods:
            print("⚠️  Aktiv mahsulot yo'q — avval `python -m app.demo_seed`.")
            return

        svc = CatalogService(CatalogRepository(db))
        added, skipped = 0, 0
        for i, p in enumerate(prods):
            has = (await db.execute(
                select(func.count()).select_from(ProductMedia).where(
                    ProductMedia.product_id == p.id,
                    ProductMedia.media_type.in_(("post", "story")),
                )
            )).scalar() or 0
            if has:
                skipped += 1
                continue
            sc = p.id.hex[:10]                      # post shortcode (unique)
            sid = str(int(p.id.hex[:15], 16))       # story media_id (unique, raqam)
            await svc.add_instagram_media(p.id, InstagramMediaCreate(
                link=f"https://www.instagram.com/p/DEMO{sc}/"))
            await svc.add_instagram_media(p.id, InstagramMediaCreate(
                link=f"https://www.instagram.com/stories/almazsilver/{sid}/"))
            added += 1

        print(f"✅ Demo IG media: {added} mahsulotga post+story biriktirildi, "
              f"{skipped} o'tkazib yuborildi (media bor).")
        print("   Ko'rish: GET /catalog/products/{id}/instagram")


if __name__ == "__main__":
    asyncio.run(main())
