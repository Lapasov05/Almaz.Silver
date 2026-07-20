"""RBAC permission registri va system rollar (TZ 13-bo'lim).

Permission kodi formati: `resource:action`.
- Standart CRUD (`view/create/update/delete/export`) har resursga generatsiya qilinadi.
- Maxsus permission'lar (approve, refund, override_ai, ...) alohida sanab o'tiladi.

`SYSTEM_ROLES` — 15 ta system rol -> permission ro'yxati (yoki ALL="*" — barchasi).
Namuna matritsa TZ 13-bo'limdan olindi; to'liq sozlanadigan matritsa Faza 6'da.
"""

# TZ 13-bo'lim: resurslar
RESOURCES: list[str] = [
    "customers",
    "orders",
    "products",
    "inventory",
    "payments",
    "delivery",
    "conversations",
    "ai",
    "employees",
    "roles",
    "settings",
    "analytics",
    "audit",
]

# Har resursga tegishli standart action'lar
CRUD_ACTIONS: list[str] = ["view", "create", "update", "delete", "export"]

# Maxsus (kontekstga xos) permission'lar — TZ 13-bo'lim matritsasi
SPECIAL_PERMISSIONS: list[str] = [
    "system_access",
    "roles:manage_roles",
    "settings:manage_settings",
    "settings:manage_integrations",
    "products:manage_products",
    "delivery:manage_delivery",
    "employees:manage_employees",
    "orders:approve",
    "orders:assign",
    "orders:refund",
    "payments:approve",
    "conversations:transfer_chat",
    "ai:override_ai",
    "ai:edit_prompt",
    "analytics:view_reports",
    "analytics:view_cost",
    "analytics:view_profit",
]

# ALL — rolga barcha permission'larni berish uchun maxsus belgi
ALL = "*"


def all_permission_codes() -> list[str]:
    """Tizimdagi barcha permission kodlari (CRUD + maxsus), tartiblangan va unikal."""
    codes = [f"{res}:{action}" for res in RESOURCES for action in CRUD_ACTIONS]
    codes += SPECIAL_PERMISSIONS
    return sorted(set(codes))


# TZ 13-bo'lim: 15 ta system rol. Namuna matritsa asosida boshlang'ich permission'lar.
# (Admin keyinchalik har katakni o'zgartira oladi — Faza 6.)
SYSTEM_ROLES: dict[str, list[str] | str] = {
    "Super Admin": ALL,
    "Owner": ALL,
    "General Manager": [
        "settings:manage_settings",
        "products:manage_products",
        "products:view",
        "customers:view",
        "conversations:view",
        "conversations:create",
        "conversations:update",
        "orders:view",
        "orders:approve",
        "payments:approve",
        "orders:refund",
        "conversations:transfer_chat",
        "ai:override_ai",
        "delivery:manage_delivery",
        "analytics:view_reports",
        "analytics:view_cost",
        "analytics:view_profit",
    ],
    "Sales Manager": [
        "products:manage_products",
        "products:view",
        "customers:view",
        "conversations:view",
        "conversations:create",
        "conversations:update",
        "conversations:transfer_chat",
        "orders:view",
        "orders:create",
        "orders:update",
        "ai:override_ai",
    ],
    "Operator": [
        "products:view",
        "customers:view",
        "conversations:view",
        "conversations:create",
        "conversations:update",
        "conversations:transfer_chat",
        "orders:view",
        "ai:override_ai",
    ],
    "Support": [
        "customers:view",
        "conversations:view",
        "conversations:create",
        "conversations:update",
        "conversations:transfer_chat",
        "orders:view",
    ],
    "Warehouse": [
        "products:view",
        "inventory:view",
        "inventory:update",
        "orders:view",
        "delivery:view",
        "delivery:manage_delivery",
    ],
    "Courier Manager": [
        "orders:view",
        "delivery:view",
        "delivery:manage_delivery",
    ],
    "Finance": [
        "orders:view",
        "orders:approve",
        "orders:refund",
        "payments:view",
        "payments:approve",
        "analytics:view_reports",
        "analytics:view_cost",
        "analytics:view_profit",
    ],
    "Marketing": [
        "products:view",
        "customers:view",
        "analytics:view_reports",
    ],
    "Content Manager": [
        "products:view",
        "products:create",
        "products:update",
        "products:manage_products",
    ],
    "AI Manager": [
        "ai:view",
        "ai:override_ai",
        "ai:edit_prompt",
        "conversations:view",
        "products:view",
    ],
    "Analyst": [
        "orders:view",
        "analytics:view_reports",
        "analytics:view_cost",
        "analytics:view_profit",
    ],
    "Auditor": [
        "orders:view",
        "payments:view",
        "customers:view",
        "audit:view",
        "analytics:view_reports",
        "analytics:view_cost",
        "analytics:view_profit",
    ],
    "Guest": [],
}
