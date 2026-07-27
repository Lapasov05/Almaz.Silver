"""Barcha ORM modellarni bitta joyда import qilib `Base.metadata`ни to'ldiradi.

Nega kerak: Celery worker faqat task import zanjiridagi modellarni ko'radi. Agar biror
model (masalan identity `User`) import qilinmasa, unga FK bergan jadvallar
(`conversation.assigned_operator_id -> user.id`) `flush` paytida `NoReferencedTableError`
beradi. Shu modulni import qilish metadata'ни to'liq qiladi.

Ishlatish: `import app.core.models_registry  # noqa: F401` (celery_app va h.k.).
Yangi modul qo'shilganда shu yerга import qo'shiladi (migrations/env.py bilan bir xil ro'yxat).
"""
from app.modules.ai import models as _ai_models  # noqa: F401
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.delivery import models as _delivery_models  # noqa: F401
from app.modules.identity import models as _identity_models  # noqa: F401
from app.modules.inbox import models as _inbox_models  # noqa: F401
from app.modules.integrations import models as _integrations_models  # noqa: F401
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.orders import models as _orders_models  # noqa: F401
from app.modules.payments import models as _payments_models  # noqa: F401
from app.modules.settings import models as _settings_models  # noqa: F401
