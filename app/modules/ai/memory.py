import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inbox.models import Conversation
from app.modules.inbox.repository import InboxRepository

TOOL_TRACE_RECENT_TURNS = 4
IMAGE_RECENT_TURNS = 6
RETURN_GAP_HOURS = 6


def _gap_note(previous, message) -> str | None:
    """Mijoz uzoq tanaffusdan keyin qayta yozgan bo'lsa — AI qayta salomlashishi uchun belgi."""
    if previous is None:
        return "[Suhbatning birinchi xabari]"
    started = getattr(previous, "created_at", None)
    now = getattr(message, "created_at", None)
    if started is None or now is None:
        return None
    hours = (now - started).total_seconds() / 3600
    if hours < RETURN_GAP_HOURS:
        return None
    days = int(hours // 24)
    if days >= 1:
        return f"[Mijoz {days} kundan keyin qayta yozdi]"
    return f"[Mijoz {int(hours)} soatdan keyin qayta yozdi]"


def _replied_message_note(target, is_self_reply: bool) -> str:
    who = "o'z xabariga" if is_self_reply else "bizning xabarga"
    if target is None:
        return f"[Mijoz {who} javob berdi]"
    snippet = (target.content or "").strip()
    products = (target.tool_call or {}).get("products") or []
    if products:
        listed = ", ".join(f"{p['position']}) {p['name']} (product_id={p['product_id']})" for p in products)
        snippet = f"{snippet} yuborilgan mahsulot kartalari: {listed}".strip()
    return f"[Mijoz {who} javob berdi: {snippet[:400]}]"


def _customer_notes(message, by_external_id: dict, with_images: bool) -> tuple[list[str], list[dict]]:
    notes: list[str] = []
    images: list[dict] = []
    for attachment in message.attachments or []:
        if not isinstance(attachment, dict):
            continue
        atype = (attachment.get("type") or "").lower()
        url = attachment.get("url")
        if atype in {"image", "photo"}:
            # Eski IG havolalari muddati o'tadi — faqat so'nggi rasmlar modelga yuboriladi
            if url and with_images:
                images.append({"type": "input_image", "image_url": url})
            else:
                notes.append("[Mijoz rasm yubordi]")
        elif atype == "ig_story":
            story_ref = attachment.get("story_ref")
            if story_ref:
                notes.append(f"[Mijoz Instagram story'ga javob berdi, story_ref={story_ref}]")
            else:
                notes.append("[Mijoz Instagram story'ga javob berdi]")
        elif atype == "reply":
            target = by_external_id.get(attachment.get("reply_to_external_id"))
            notes.append(_replied_message_note(target, bool(attachment.get("is_self_reply"))))
        elif atype == "template":
            continue
        elif atype:
            notes.append(f"[Mijoz {atype} yubordi]")
    return notes, images


async def build_conversation_input(
    db: AsyncSession,
    conversation: Conversation,
    message_limit: int,
) -> list[dict]:
    result: list[dict] = []
    history = await InboxRepository(db).list_recent_messages(conversation.id, message_limit)
    by_external_id = {m.external_id: m for m in history if m.external_id}
    traced = [m for m in history if (m.tool_call or {}).get("calls")]
    trace_ids = {m.id for m in traced[-TOOL_TRACE_RECENT_TURNS:]}
    with_media = [
        m for m in history
        if m.sender_type == "customer" and any(
            isinstance(a, dict) and (a.get("type") or "").lower() in {"image", "photo"} and a.get("url")
            for a in (m.attachments or [])
        )
    ]
    image_ids = {m.id for m in with_media[-IMAGE_RECENT_TURNS:]}

    gap_notes: dict = {}
    previous = None
    for message in history:
        if message.sender_type == "customer":
            note = _gap_note(previous, message)
            if note:
                gap_notes[message.id] = note
        previous = message

    for message in history:
        if message.sender_type == "customer":
            notes, images = _customer_notes(message, by_external_id, message.id in image_ids)
            gap = gap_notes.get(message.id)
            if gap:
                notes.append(gap)
            text = "\n".join(part for part in [(message.content or "").strip(), *notes] if part)
            content: list[dict] = []
            if text:
                content.append({"type": "input_text", "text": text})
            content.extend(images)
            if content:
                result.append({"role": "user", "content": content})
            continue
        if message.sender_type not in {"ai", "operator", "system"}:
            continue
        text = (message.content or "").strip()
        metadata = message.tool_call or {}
        products = metadata.get("products") if metadata.get("name") == "send_product_images" else None
        if products:
            ordered = ", ".join(
                f"{item['position']}-mahsulot: {item['name']} "
                f"(product_id={item['product_id']}, variant_id={item['variant_id']})"
                for item in products
            )
            text = f"{text}\n[Yuborilgan carousel tartibi: {ordered}]".strip()
        if message.id in trace_ids and metadata.get("calls"):
            serialized = json.dumps(metadata["calls"], ensure_ascii=False, default=str)
            text = f"{text}\n[Oldingi function natijalari: {serialized[:6000]}]".strip()
        if message.sender_type == "operator" and text:
            text = f"[Operator yozdi] {text}"
        elif message.sender_type == "system" and text:
            text = f"[Tizim xabari] {text}"
        if text:
            result.append({"role": "assistant", "content": text})
    return result
