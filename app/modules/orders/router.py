"""orders CRM API (TZ 10), RBAC bilan himoyalangan."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params
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
    response_model=Page[OrderOut],
    dependencies=[Depends(require_permission("orders:view"))],
)
async def list_orders(
    service: OrdersService = Depends(get_orders_service),
    pp: PageParams = Depends(page_params),
    status: OrderStatus | None = None,
    customer_id: uuid.UUID | None = None,
    assigned_operator_id: uuid.UUID | None = None,
    created_by_ai: bool | None = None,
    order_no: str | None = Query(default=None, description="Buyurtma raqami bo'yicha"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Page[OrderOut]:
    items, total = await service.list(
        pp=pp, status=status.value if status else None, customer_id=customer_id,
        assigned_operator_id=assigned_operator_id, created_by_ai=created_by_ai,
        order_no=order_no, date_from=date_from, date_to=date_to,
    )
    return Page(items=[OrderOut.model_validate(o) for o in items], total=total, limit=pp.limit, offset=pp.offset)


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
