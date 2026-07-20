"""payments CRM API (TZ 12), RBAC bilan.

Tasdiq/rad: `payments:approve` (Finance/Owner/GM). Karta boshqaruvi: `settings:manage_settings`.
Chek yuklash: `payments:view`.
"""
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
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
    response_model=list[PaymentCardOut],
    dependencies=[Depends(require_permission("payments:view"))],
)
async def list_cards(service: PaymentCardService = Depends(get_card_service)) -> list[PaymentCardOut]:
    return [PaymentCardOut.model_validate(c) for c in await service.list_cards()]


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
    response_model=list[PaymentOut],
    dependencies=[Depends(require_permission("payments:view"))],
)
async def list_payments(
    service: PaymentService = Depends(get_payment_service),
    status: PaymentStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PaymentOut]:
    payments = await service.list(status=status.value if status else None, limit=limit, offset=offset)
    return [PaymentOut.model_validate(p) for p in payments]


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
