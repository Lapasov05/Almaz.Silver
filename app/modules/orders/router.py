"""orders CRM API (TZ 10), RBAC bilan himoyalangan."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.modules.identity.models import User
from app.modules.orders.models import OrderStatus
from app.modules.orders.schemas import OrderCancel, OrderCreate, OrderOut
from app.modules.orders.service import OrdersService

router = APIRouter(prefix="/orders", tags=["orders"])


def get_orders_service(db: AsyncSession = Depends(get_db)) -> OrdersService:
    return OrdersService(db)


@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    service: OrdersService = Depends(get_orders_service),
    user: User = Depends(require_permission("orders:create")),
) -> OrderOut:
    order = await service.create_order(payload.customer_id, payload.items, changed_by=user.id)
    return OrderOut.model_validate(order)


@router.get(
    "",
    response_model=list[OrderOut],
    dependencies=[Depends(require_permission("orders:view"))],
)
async def list_orders(
    service: OrdersService = Depends(get_orders_service),
    status: OrderStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[OrderOut]:
    orders = await service.list(status=status.value if status else None, limit=limit, offset=offset)
    return [OrderOut.model_validate(o) for o in orders]


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    dependencies=[Depends(require_permission("orders:view"))],
)
async def get_order(
    order_id: uuid.UUID, service: OrdersService = Depends(get_orders_service)
) -> OrderOut:
    return OrderOut.model_validate(await service.get(order_id))


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: uuid.UUID,
    payload: OrderCancel,
    service: OrdersService = Depends(get_orders_service),
    user: User = Depends(require_permission("orders:update")),
) -> OrderOut:
    """Buyurtmani bekor qiladi va zaxirani bo'shatadi (reserved_qty--)."""
    return OrderOut.model_validate(await service.cancel_order(order_id, changed_by=user.id))
