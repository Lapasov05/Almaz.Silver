"""Conversation state machine (TZ 7.1).

greeting → browsing → recommending → ordering → awaiting_location →
awaiting_payment → payment_review → handed_off → closed
"""
from app.modules.inbox.models import AiState

# Ruxsat etilgan o'tishlar (yo'naltirilgan graf). handed_off/closed — har qayerdan.
VALID_TRANSITIONS: dict[AiState, set[AiState]] = {
    AiState.greeting: {AiState.browsing, AiState.recommending, AiState.handed_off, AiState.closed},
    AiState.browsing: {AiState.recommending, AiState.ordering, AiState.handed_off, AiState.closed},
    AiState.recommending: {AiState.browsing, AiState.ordering, AiState.handed_off, AiState.closed},
    AiState.ordering: {AiState.awaiting_location, AiState.recommending, AiState.handed_off, AiState.closed},
    AiState.awaiting_location: {AiState.awaiting_payment, AiState.ordering, AiState.handed_off, AiState.closed},
    AiState.awaiting_payment: {AiState.payment_review, AiState.handed_off, AiState.closed},
    AiState.payment_review: {AiState.handed_off, AiState.closed},
    AiState.handed_off: {AiState.closed, AiState.browsing},
    AiState.closed: {AiState.greeting, AiState.browsing},
}


def can_transition(current: AiState, target: AiState) -> bool:
    if current == target:
        return True
    return target in VALID_TRANSITIONS.get(current, set())


def infer_next_state(current: AiState, used_tools: list[str]) -> AiState:
    """Ishlatilgan tool'lardan keyingi holatni aniqlaydi.

    Kuchli signal beruvchi (haqiqatan sodir bo'lgan) harakatlar — avtoritativ:
    handoff / request_location / create_order.
    """
    if "handoff_to_operator" in used_tools:
        return AiState.handed_off
    if "submit_payment" in used_tools:
        return AiState.payment_review
    if "get_payment_card" in used_tools:
        return AiState.awaiting_payment if can_transition(current, AiState.awaiting_payment) else current
    if "request_location" in used_tools:
        return AiState.awaiting_location
    if "create_order" in used_tools:
        return AiState.ordering
    if any(t in used_tools for t in ("search_product", "get_product_details", "recommend", "check_stock")):
        return AiState.recommending if can_transition(current, AiState.recommending) else current
    if current == AiState.greeting:
        return AiState.browsing
    return current
