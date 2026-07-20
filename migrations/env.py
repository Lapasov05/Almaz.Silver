"""Alembic async muhiti — Settings'dan DB URL oladi, model metadata'sini yig'adi."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.base_model import Base
from app.core.config import get_settings

# Model metadata'si to'lishi uchun barcha modellarni import qilamiz.
# (Yangi modul qo'shilganда shu yerga import qo'shiladi.)
from app.modules.ai import models as _ai_models  # noqa: F401
from app.modules.audit import models as _audit_models  # noqa: F401
from app.modules.catalog import models as _catalog_models  # noqa: F401
from app.modules.delivery import models as _delivery_models  # noqa: F401
from app.modules.identity import models as _identity_models  # noqa: F401
from app.modules.inbox import models as _inbox_models  # noqa: F401
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.orders import models as _orders_models  # noqa: F401
from app.modules.payments import models as _payments_models  # noqa: F401
from app.modules.settings import models as _settings_models  # noqa: F401

config = context.config

# DB URL kodda emas — Settings (env) orqali (TZ 15-bo'lim)
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
