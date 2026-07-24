"""payments CRM API (TZ 12), RBAC bilan.

Tasdiq/rad: `payments:approve` (Finance/Owner/GM). Karta boshqaruvi: `settings:manage_settings`.
Chek yuklash: `payments:view`.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.pagination import Page, PageParams, page_params, page_params_ref
from app.modules.identity.models import User
from app.modules.payments.models import PaymentStatus
from app.modules.payments.schemas import (
    PaymentCardCreate,
    PaymentCardOut,
    PaymentCardUpdate,
    PaymentOut,
    PaymentReject,
    PaymentSubmit,
    ReceiptUploadOut,
)
from app.modules.payments.service import PaymentCardService, PaymentService
from app.modules.payments.storage import ReceiptStorage

router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_service(db: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


def get_card_service(db: AsyncSession = Depends(get_db)) -> PaymentCardService:
    return PaymentCardService(db)


# ==================== Payment cards (asosiy karta) ====================
@router.get(
    "/cards",
    response_model=Page[PaymentCardOut],
    dependencies=[Depends(require_permission("payments:view"))],
)
async def list_cards(
    is_active: bool | None = None,
    pp: PageParams = Depends(page_params_ref),
    service: PaymentCardService = Depends(get_card_service),
) -> Page[PaymentCardOut]:
    items, total = await service.list_cards(is_active=is_active, pp=pp)
    return Page(items=[PaymentCardOut.model_validate(c) for c in items], total=total, limit=pp.limit, offset=pp.offset)


@router.get(
    "/cards/{card_id}",
    response_model=PaymentCardOut,
    dependencies=[Depends(require_permission("payments:view"))],
)
async def get_card(card_id: uuid.UUID, service: PaymentCardService = Depends(get_card_service)) -> PaymentCardOut:
    return PaymentCardOut.model_validate(await service.get(card_id))


@router.delete(
    "/cards/{card_id}",
    status_code=204,
    dependencies=[Depends(require_permission("settings:manage_settings"))],
)
async def delete_card(card_id: uuid.UUID, service: PaymentCardService = Depends(get_card_service)) -> None:
    await service.delete(card_id)


@router.post(
    "/cards",
    response_model=PaymentCardOut,
    dependencies=[Depends(require_permission("settings:manage_settings"))],
)
async def create_card(
    payload: PaymentCardCreate, service: PaymentCardService = Depends(get_card_service)
) -> PaymentCardOut:
    return PaymentCardOut.model_validate(await service.create(payload.model_dump()))


@router.patch(
    "/cards/{card_id}",
    response_model=PaymentCardOut,
    dependencies=[Depends(require_permission("settings:manage_settings"))],
)
async def update_card(
    card_id: uuid.UUID,
    payload: PaymentCardUpdate,
    service: PaymentCardService = Depends(get_card_service),
) -> PaymentCardOut:
    return PaymentCardOut.model_validate(await service.update(card_id, payload.model_dump(exclude_unset=True)))


# ==================== Chek yuklash (object storage) ====================
@router.post(
    "/receipts",
    response_model=ReceiptUploadOut,
    dependencies=[Depends(require_permission("payments:view"))],
)
async def upload_receipt(file: UploadFile = File(...)) -> ReceiptUploadOut:
    """Chek rasmini object storage'ga yuklaydi (TZ 12)."""
    data = await file.read()
    ext = (file.filename or "receipt.jpg").rsplit(".", 1)[-1].lower()
    url, key = await ReceiptStorage().upload(
        data, content_type=file.content_type or "image/jpeg", ext=ext
    )
    return ReceiptUploadOut(url=url, key=key)


# ==================== Payment ====================
@router.post(
    "/submit",
    response_model=PaymentOut,
    dependencies=[Depends(require_permission("payments:view"))],
)
async def submit_payment(
    payload: PaymentSubmit, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    payment = await service.submit_payment(payload.order_id, payload.receipt_url, payload.payer_name)
    return PaymentOut.model_validate(payment)


@router.get(
    "",
    response_model=Page[PaymentOut],
    dependencies=[Depends(require_permission("payments:view"))],
)
async def list_payments(
    service: PaymentService = Depends(get_payment_service),
    pp: PageParams = Depends(page_params),
    status: PaymentStatus | None = None,
    order_id: uuid.UUID | None = None,
    reviewed_by: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Page[PaymentOut]:
    items, total = await service.list(
        pp=pp, status=status.value if status else None, order_id=order_id,
        reviewed_by=reviewed_by, date_from=date_from, date_to=date_to,
    )
    return Page(items=[PaymentOut.model_validate(p) for p in items], total=total, limit=pp.limit, offset=pp.offset)


@router.get(
    "/{payment_id}",
    response_model=PaymentOut,
    dependencies=[Depends(require_permission("payments:view"))],
)
async def get_payment(
    payment_id: uuid.UUID, service: PaymentService = Depends(get_payment_service)
) -> PaymentOut:
    return PaymentOut.model_validate(await service.get(payment_id))


@router.post("/{payment_id}/approve", response_model=PaymentOut)
async def approve_payment(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service),
    user: User = Depends(require_permission("payments:approve")),
) -> PaymentOut:
    """To'lovni tasdiqlaydi (idempotent) → stock_qty--, buyurtma confirmed."""
    return PaymentOut.model_validate(await service.approve(payment_id, user.id))


@router.post("/{payment_id}/reject", response_model=PaymentOut)
async def reject_payment(
    payment_id: uuid.UUID,
    payload: PaymentReject,
    service: PaymentService = Depends(get_payment_service),
    user: User = Depends(require_permission("payments:approve")),
) -> PaymentOut:
    return PaymentOut.model_validate(await service.reject(payment_id, user.id, payload.reason))
