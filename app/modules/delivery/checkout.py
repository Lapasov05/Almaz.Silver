"""Public checkout / map sahifasi API (TZ 11) — OCHIQ, bir martalik token bilan himoyalangan.

Mijoz IG/TG orqali kelgan xarita linkini ochadi: `{frontend_map_url}/map/{token}`.
IKKI QADAMLI oqim:
  1) POST /map/{token}/resolve  {lat,lng}                 → zona + narx + (BTS bo'lsa) filiallar (token YOPILMAYDI)
  2) POST /map/{token}/confirm  {lat,lng, bts_branch_id?} → saqlanadi, token yopiladi
Toshkent bo'lsa filial tanlash yo'q — resolve bo'sh ro'yxat qaytaradi, confirm to'g'ridan yakunlaydi.
Endpoint'lar `/map/{token}/...` va `/checkout/{token}/...` (bir xil).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.schemas import (
    BtsBranchOut,
    BtsBranchWithDistanceOut,
    CheckoutContextOut,
    CheckoutResultOut,
    LocationConfirmIn,
    LocationResolveIn,
    LocationResolveOut,
)
from app.modules.delivery.service import DeliveryService
from app.modules.orders.repository import OrdersRepository

router = APIRouter(tags=["checkout"])

_MAX_BRANCHES = 30  # ro'yxat juda uzun bo'lmasin (eng yaqin 30 ta)


def get_delivery_service(db: AsyncSession = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db)


async def _context(token: str, service: DeliveryService) -> CheckoutContextOut:
    ctx = await service.get_checkout_context(token)
    return CheckoutContextOut(**ctx)


async def _resolve(token: str, payload: LocationResolveIn, service: DeliveryService) -> LocationResolveOut:
    """1-qadam: zona/narx + (BTS bo'lsa) filiallar ro'yxati. Token yopilmaydi."""
    r = await service.preview_location(token, payload.lat, payload.lng)
    order = r["order"]
    fee = r["fee"]
    branches = [
        BtsBranchWithDistanceOut(**BtsBranchOut.model_validate(b).model_dump(), distance_km=round(d, 1))
        for b, d in r["branches"][:_MAX_BRANCHES]
    ]
    is_bts = r["location_type"].value == "BTS"
    return LocationResolveOut(
        order_no=order.order_no,
        location_type=r["location_type"],
        delivery_fee=fee,
        items_total=order.items_total,
        grand_total=order.items_total + fee,
        requires_branch_selection=is_bts,
        branches=branches,
    )


async def _confirm(token: str, payload: LocationConfirmIn, service: DeliveryService,
                   db: AsyncSession) -> CheckoutResultOut:
    """2-qadam: tanlangan filial (BTS) yoki Toshkent — saqlanadi, token yopiladi."""
    delivery = await service.confirm_location(
        token,
        lat=payload.lat,
        lng=payload.lng,
        bts_branch_id=payload.bts_branch_id,
        address_text=payload.address_text,
        phone=payload.phone,
        landmark=payload.landmark,
        apartment=payload.apartment,
    )
    order = await OrdersRepository(db).get(delivery.order_id)
    branch = None
    if delivery.bts_branch_id is not None:
        b = await DeliveryRepository(db).get_bts_branch(delivery.bts_branch_id)
        branch = BtsBranchOut.model_validate(b) if b is not None else None
    return CheckoutResultOut(
        order_no=order.order_no,
        location_type=delivery.location_type,
        delivery_fee=delivery.fee,
        items_total=order.items_total,
        grand_total=order.grand_total,
        address_text=delivery.address_text,
        bts_branch=branch,
    )


def _register(prefix: str) -> None:
    """`/map/{token}/...` va `/checkout/{token}/...` uchun bir xil endpointlarni ro'yxatga oladi."""

    @router.get(f"/{prefix}/{{token}}", response_model=CheckoutContextOut, name=f"{prefix}_context")
    async def context(token: str, service: DeliveryService = Depends(get_delivery_service)):
        return await _context(token, service)

    @router.post(f"/{prefix}/{{token}}/resolve", response_model=LocationResolveOut, name=f"{prefix}_resolve")
    async def resolve(token: str, payload: LocationResolveIn,
                      service: DeliveryService = Depends(get_delivery_service)):
        return await _resolve(token, payload, service)

    @router.post(f"/{prefix}/{{token}}/confirm", response_model=CheckoutResultOut, name=f"{prefix}_confirm")
    async def confirm(token: str, payload: LocationConfirmIn,
                      service: DeliveryService = Depends(get_delivery_service),
                      db: AsyncSession = Depends(get_db)):
        return await _confirm(token, payload, service, db)


_register("map")
_register("checkout")
