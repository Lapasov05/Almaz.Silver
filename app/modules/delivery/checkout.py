"""Public checkout / map sahifasi API (TZ 11) — OCHIQ, bir martalik token bilan himoyalangan.

Mijoz IG/TG orqali kelgan xarita linkini ochadi: `{frontend_map_url}/map/{token}`.
Frontend lat/lng ni backendga qaytaradi → zona (Toshkent/BTS) aniqlanadi, narx qo'shiladi.
Token: muddatli, bir martalik. Endpoint'lar `/checkout/{token}` va `/map/{token}` (bir xil).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.schemas import (
    BtsBranchOut,
    CheckoutContextOut,
    CheckoutResultOut,
    CheckoutSubmit,
)
from app.modules.delivery.service import DeliveryService
from app.modules.orders.repository import OrdersRepository

router = APIRouter(tags=["checkout"])


def get_delivery_service(db: AsyncSession = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db)


async def _context(token: str, service: DeliveryService) -> CheckoutContextOut:
    ctx = await service.get_checkout_context(token)
    return CheckoutContextOut(**ctx)


async def _submit(token: str, payload: CheckoutSubmit, service: DeliveryService,
                  db: AsyncSession) -> CheckoutResultOut:
    """Mijoz lokatsiyani yuboradi → buyurtmaga bog'lanadi, narx qo'shiladi, token yopiladi.

    Toshkent ichida bo'lsa type=Toshkent (50k); tashqarida bo'lsa type=BTS (30k) + eng yaqin filial.
    """
    delivery = await service.resolve_checkout(
        token,
        lat=payload.lat,
        lng=payload.lng,
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


# --- /checkout/{token} (backend API) ---
@router.get("/checkout/{token}", response_model=CheckoutContextOut)
async def checkout_context(token: str, service: DeliveryService = Depends(get_delivery_service)):
    return await _context(token, service)


@router.post("/checkout/{token}", response_model=CheckoutResultOut)
async def checkout_submit(token: str, payload: CheckoutSubmit,
                          service: DeliveryService = Depends(get_delivery_service),
                          db: AsyncSession = Depends(get_db)):
    return await _submit(token, payload, service, db)


# --- /map/{token} (frontend map sahifasi shu API'ni chaqiradi — bir xil xatti-harakat) ---
@router.get("/map/{token}", response_model=CheckoutContextOut)
async def map_context(token: str, service: DeliveryService = Depends(get_delivery_service)):
    return await _context(token, service)


@router.post("/map/{token}", response_model=CheckoutResultOut)
async def map_submit(token: str, payload: CheckoutSubmit,
                     service: DeliveryService = Depends(get_delivery_service),
                     db: AsyncSession = Depends(get_db)):
    return await _submit(token, payload, service, db)
