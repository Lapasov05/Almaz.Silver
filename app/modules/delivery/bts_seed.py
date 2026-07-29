"""BTS filiallarini bot_branches.json'dan bazaga yuklash (idempotent).

Struktura: {"<region>": {"<district>": [{Id, Filial, Manzil, Moljal, IshVaqtlari, Telefon,
Map:{lat,lon}}, ...]}}. ext_id (BTS "Id") bo'yicha upsert — takror ishga tushirilsa yangilanadi.
Dinamik: keyin admin API orqali yangi filial qo'sha oladi (bu faqat boshlang'ich yuklash).
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.delivery.models import BtsBranch

_DATA_FILE = Path(__file__).parent / "data" / "bts_branches.json"


def _load_rows() -> list[dict]:
    data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for region, districts in data.items():
        for district, branches in districts.items():
            for b in branches:
                m = b.get("Map") or {}
                lat, lon = m.get("lat"), m.get("lon")
                if lat is None or lon is None:
                    continue  # koordinatasiz filial — eng yaqinni topib bo'lmaydi, o'tkazamiz
                rows.append({
                    "ext_id": str(b.get("Id") or "").strip(),
                    "name": (b.get("Filial") or "").strip()[:150] or "BTS",
                    "region": region[:120],
                    "district": district[:120],
                    "address": b.get("Manzil"),
                    "landmark": (b.get("Moljal") or None),
                    "phone": (str(b.get("Telefon")) if b.get("Telefon") is not None else None),
                    "work_hours": (b.get("IshVaqtlari") or None),
                    "lat": lat,
                    "lng": lon,
                })
    return rows


async def seed_bts_branches(db: AsyncSession) -> dict:
    """bts_branch jadvalini to'ldiradi/yangilaydi. Qaytadi: {created, updated, total}."""
    rows = _load_rows()
    existing = {
        b.ext_id: b for b in (await db.execute(select(BtsBranch))).scalars().all()
    }
    created = updated = 0
    for r in rows:
        if not r["ext_id"]:
            continue
        b = existing.get(r["ext_id"])
        if b is None:
            db.add(BtsBranch(**r))
            created += 1
        else:  # koordinata/manzil o'zgargan bo'lishi mumkin — yangilaymiz
            for k, v in r.items():
                setattr(b, k, v)
            updated += 1
    await db.flush()
    return {"created": created, "updated": updated, "total": len(rows)}
