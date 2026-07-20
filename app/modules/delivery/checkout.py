"""Public checkout sahifasi API (TZ 11) — OCHIQ, faqat bir martalik token bilan himoyalangan.

Mijoz IG/TG orqali kelgan linkni ochadi: Toshkent — xarita pin (lat/lng),
viloyat — BTS struktura manzil (address_text). Token: muddatli, bir martalik.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.delivery.schemas import (
    CheckoutContextOut,
    CheckoutSubmit,
    DeliveryOut,
)
from app.modules.delivery.service import DeliveryService

router = APIRouter(prefix="/checkout", tags=["checkout"])


def get_delivery_service(db: AsyncSession = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db)


@router.get("/{token}", response_model=CheckoutContextOut)
async def checkout_context(
    token: str, service: DeliveryService = Depends(get_delivery_service)
) -> CheckoutContextOut:
    """Sahifa ma'lumoti: buyurtma xulosasi + zona narxlari (token tekshiriladi)."""
    ctx = await service.get_checkout_context(token)
    return CheckoutContextOut(**ctx)


@router.post("/{token}", response_model=DeliveryOut)
async def checkout_submit(
    token: str,
    payload: CheckoutSubmit,
    service: DeliveryService = Depends(get_delivery_service),
) -> DeliveryOut:
    """Mijoz lokatsiyani yuboradi → buyurtmaga bog'lanadi, narx qo'shiladi, token yopiladi."""
    delivery = await service.resolve_checkout(
        token,
        zone=payload.zone.value,
        address_text=payload.address_text,
        lat=payload.lat,
        lng=payload.lng,
    )
    return DeliveryOut.model_validate(delivery)
