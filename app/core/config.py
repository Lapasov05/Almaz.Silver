"""Ilova konfiguratsiyasi — pydantic-settings orqali muhit o'zgaruvchilaridan tiplab yuklanadi.

TZ 15-bo'lim: barcha secretlar .env / secret manager'dan keladi, kodda hardcode qilinmaydi.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Umumiy ---
    app_name: str = "Almaz AI Seller CRM"
    environment: str = "development"
    debug: bool = True

    # --- PostgreSQL ---
    postgres_user: str = "almaz"
    postgres_password: str = "almaz"
    postgres_db: str = "almaz"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # --- JWT (TZ 15-bo'lim) ---
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    permission_cache_ttl: int = 300  # permission cache TTL (soniya) — TZ 13-bo'lim

    # --- RabbitMQ / Celery ---
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "redis://redis:6379/1"
    celery_task_always_eager: bool = False  # test/dev: broker'siz inline ishlash

    # --- Telegram (bazaviy URL + knoblar; TOKENLAR integration_config'да, env'да EMAS) ---
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_auto_webhook: bool = True  # ishga tushganда webhook'ni avtomatik ulash

    # --- Instagram / Meta Graph API (bazaviy URL; TOKENLAR DB'да) ---
    instagram_graph_version: str = "v21.0"
    instagram_graph_base_url: str = "https://graph.facebook.com"
    # Aktiv storylar ro'yxati (me/stories) Instagram Login tokeni bilan shu hostda ochiladi
    instagram_stories_base_url: str = "https://graph.instagram.com"

    # --- Umumiy HTTP ---
    http_timeout_seconds: float = 10.0

    # --- Checkout / lokatsiya (TZ 11) ---
    public_base_url: str = "http://localhost:8000"  # rasm/statik + backend uchun tashqi bazaviy URL
    checkout_path: str = "/checkout"                 # (legacy) backend checkout API yo'li
    # Mijozga yuboriladigan LOKATSIYA (xarita) linki — frontend sahifasi:
    #   {frontend_map_url}/map/{token}. Frontend lat/lng ni backendga qaytaradi.
    frontend_map_url: str = "https://almaz-steel.vercel.app"
    # Yetkazish zonasi — Toshkent bounding box (lat/lng'dan AVTOMATIK zona aniqlash)
    delivery_tashkent_lat_min: float = 41.15
    delivery_tashkent_lat_max: float = 41.40
    delivery_tashkent_lng_min: float = 69.10
    delivery_tashkent_lng_max: float = 69.50
    checkout_token_expiry_hours: int = 24           # bir martalik token muddati

    # --- CORS (frontend ulanishi uchun) ---
    # Vergul bilan ajratilgan origin ro'yxati. Prod frontend domenini shu yerga qo'shing.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"   # Vite (React/Vue) dev
        "http://localhost:3000,http://127.0.0.1:3000,"   # Next.js / CRA dev
        "https://almaz-steel.vercel.app"                 # prod frontend (Vercel)
    )
    # Ixtiyoriy regex (masalan barcha subdomenlar): r"https://.*\.cognilabs\.org"
    cors_origin_regex: str = ""
    cors_allow_credentials: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- File upload (POST /files -> URL) ---
    upload_dir: str = "/code/uploads"   # volume; nginx orqali /uploads bilan ochiladi
    upload_max_mb: int = 10

    # --- API hujjatlari (/docs, /redoc, /openapi.json) himoyasi ---
    docs_auth_enabled: bool = True
    docs_username: str = "admin"
    docs_password: str = "almaz-docs"  # prod'da ALBATTA almashtiring

    # --- Hardening (TZ 15/16/17, Faza 7) ---
    rate_limit_enabled: bool = True
    rate_limit_login_per_min: int = 10       # login brute-force himoyasi
    rate_limit_webhook_per_min: int = 240    # IG/TG webhook
    rate_limit_default_per_min: int = 120
    # Proaktiv qayta jalb (IG 24-soat oynasi)
    reengagement_enabled: bool = False
    reengagement_interval_minutes: int = 30      # Celery beat davri
    reengagement_inactivity_minutes: int = 120   # shu vaqtdan jim bo'lsa
    reengagement_window_hours: int = 24          # IG 24h oynasi ichida bo'lsa

    # --- AI / LLM (TZ 7-bo'lim). OpenAI api_key -> integration_config (DB), env'да EMAS ---
    # llm_provider: "openai" (real, DB'да kalit) | "fake" (dev/test, kalitsiz) | "none"
    llm_provider: str = "openai"
    ai_default_model: str = "gpt-5-mini"
    ai_memory_message_count: int = 0        # 0 = cheklovsiz: AI butun suhbatni ko'radi
    ai_max_tool_iterations: int = 16        # tool-calling sikli chegarasi (mahsulot+quti rasmlari + buyurtma ko'p tool chaqiradi)
    ai_reply_delay_seconds: float = 7.0     # javob oldidan insonsimon pauza (typing ko'rinadi)

    # --- MinIO / S3 ---
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "almaz"

    # --- Boshlang'ich Super Admin (seed) ---
    seed_admin_email: str = "admin@almazsilver.uz"
    seed_admin_password: str = "admin123"
    seed_admin_name: str = "Super Admin"

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — har chaqiruvda qayta o'qimaslik uchun keshlanadi."""
    return Settings()
