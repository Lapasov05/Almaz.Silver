"""delivery CRM API — checkout link generatsiya + yetkazish holati (TZ 11), RBAC bilan."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.delivery.schemas import (
    CheckoutLinkOut,
    DeliveryOut,
    DeliveryStatusUpdate,
)
from app.modules.delivery.service import DeliveryService

router = APIRouter(prefix="/delivery", tags=["delivery"])


def get_delivery_service(db: AsyncSession = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db)


@router.post(
    "/orders/{order_id}/checkout-link",
    response_model=CheckoutLinkOut,
    dependencies=[Depends(require_permission("orders:update"))],
)
async def create_checkout_link(
    order_id: uuid.UUID, service: DeliveryService = Depends(get_delivery_service)
) -> CheckoutLinkOut:
    """Buyurtma uchun bir martalik checkout link generatsiya qiladi (TZ 11)."""
    url, expires_at = await service.create_checkout_link(order_id)
    return CheckoutLinkOut(url=url, expires_at=expires_at)


@router.get(
    "/orders/{order_id}",
    response_model=DeliveryOut,
    dependencies=[Depends(require_permission("delivery:view"))],
)
async def get_delivery(
    order_id: uuid.UUID, service: DeliveryService = Depends(get_delivery_service)
) -> DeliveryOut:
    return DeliveryOut.model_validate(await service.get_by_order(order_id))


@router.patch(
    "/{delivery_id}/status",
    response_model=DeliveryOut,
    dependencies=[Depends(require_permission("delivery:manage_delivery"))],
)
async def update_delivery_status(
    delivery_id: uuid.UUID,
    payload: DeliveryStatusUpdate,
    service: DeliveryService = Depends(get_delivery_service),
) -> DeliveryOut:
    """Operator yetkazish holatini yangilaydi (dispatched/delivered)."""
    return DeliveryOut.model_validate(await service.update_status(delivery_id, payload.status))
