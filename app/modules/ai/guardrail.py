"""LLM Guardrail — chiqish (output) validatsiya qatlami (TZ 15-bo'lim, KRITIK).

Har AI javobi yuborishdan OLDIN shu yerdan o'tadi. Biznes qoidalari (buzilmaydi):
- Tosh DOIM "serkon toshi" — "olmos/diamond/brilliant/tabiiy tosh" bo'lmaydi.
- Material DOIM "Kumush 925 + rodiy qoplama" — "oltin/gold" bo'lmaydi.
Buzilish topilsa: taqiqlangan atama to'g'ri atama bilan almashtiriladi va qayd etiladi.
"""
import re
from dataclasses import dataclass, field

# (pattern, to'g'ri almashtiruv, buzilish kodi)
_RULES: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"\b(olmos(lar)?|diamonds?|brilliant(lar)?|бриллиант\w*|олмос\w*)\b", re.IGNORECASE | re.UNICODE),
        "serkon toshi",
        "forbidden_stone",
    ),
    (
        re.compile(r"tabiiy\s+tosh|natural\s+stone|real\s+diamond", re.IGNORECASE | re.UNICODE),
        "serkon toshi",
        "forbidden_stone",
    ),
    (
        re.compile(r"\b(oltin|gold|золото|zoloto)\b", re.IGNORECASE | re.UNICODE),
        "Kumush 925 + rodiy",
        "forbidden_material",
    ),
]


@dataclass
class GuardrailResult:
    text: str  # tozalangan (yuborishga tayyor) matn
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def enforce(text: str | None) -> GuardrailResult:
    """AI javobini biznes qoidalariga tekshiradi va tuzatadi."""
    if not text:
        return GuardrailResult(text="")
    cleaned = text
    violations: list[str] = []
    for pattern, replacement, code in _RULES:
        if pattern.search(cleaned):
            violations.append(code)
            cleaned = pattern.sub(replacement, cleaned)
    return GuardrailResult(text=cleaned, violations=violations)


# Prompt injection belgilaridagi tipik naqshlar (uz/en/ru) — TZ 15
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(above|previous|system)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b|act\s+as\b|pretend\s+to\s+be", re.IGNORECASE),
    re.compile(r"system\s*prompt|reveal\s+your\s+(prompt|instructions)", re.IGNORECASE),
    re.compile(r"oldingi\s+ko'?rsatmalar\w*\s+e'?tibor\w*\s+ber\w*", re.IGNORECASE | re.UNICODE),
    re.compile(r"игнорируй\s+(предыдущие|все)\s+инструкции", re.IGNORECASE | re.UNICODE),
]

# Xabar boshidagi rol yorlig'ini spoofing qilishga urinish (system:/assistant:)
_ROLE_SPOOF = re.compile(r"^\s*(system|assistant|developer|tool)\s*:", re.IGNORECASE)


def detect_injection(text: str | None) -> bool:
    """Matnda prompt injection urinishi bor-yo'qligini aniqlaydi (log/monitoring uchun)."""
    if not text:
        return False
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def sanitize_user_input(text: str | None, max_len: int = 4000) -> str:
    """Prompt injection'ga qarshi tozalash (TZ 15).

    Asosiy himoya — rol ajratish (system vs user). Qo'shimcha: uzunlik cheklovi,
    boshqaruv belgilarini olib tashlash, rol-yorlig'i spoofingini zararsizlantirish.
    Mazmun butunlay o'chirilmaydi — model system qoidalariga tayanadi.
    """
    if not text:
        return ""
    stripped = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    # Har qatordagi "system:/assistant:" kabi spoofing prefikslarini zararsizlantiramiz
    lines = [_ROLE_SPOOF.sub(lambda m: m.group(0).replace(":", "﹕"), ln) for ln in stripped.split("\n")]
    return "\n".join(lines)[:max_len]
