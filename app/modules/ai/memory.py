import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inbox.models import Conversation
from app.modules.inbox.repository import InboxRepository


async def build_conversation_input(
    db: AsyncSession,
    conversation: Conversation,
    message_limit: int,
) -> list[dict]:
    result: list[dict] = []
    history = await InboxRepository(db).list_recent_messages(conversation.id, message_limit)
    for message in history:
        if message.sender_type == "customer":
            content: list[dict] = []
            if message.content:
                content.append({"type": "input_text", "text": message.content})
            for attachment in message.attachments or []:
                if not isinstance(attachment, dict):
                    continue
                image_url = attachment.get("url")
                if attachment.get("type") in {"image", "photo"} and image_url:
                    content.append({"type": "input_image", "image_url": image_url})
                elif attachment.get("type") in {"image", "photo"}:
                    content.append({"type": "input_text", "text": "[Mijoz rasm yubordi]"})
            if content:
                result.append({"role": "user", "content": content})
            continue
        if message.sender_type not in {"ai", "operator"}:
            continue
        text = message.content or ""
        metadata = message.tool_call or {}
        products = metadata.get("products") if metadata.get("name") == "send_product_images" else None
        if products:
            ordered = "; ".join(
                f"{item['position']}-mahsulot: {item['name']} "
                f"(product_id={item['product_id']}, variant_id={item['variant_id']})"
                for item in products
            )
            text = f"{text}\n[Oldingi carousel tartibi: {ordered}]".strip()
        calls = metadata.get("calls")
        if calls:
            serialized = json.dumps(calls, ensure_ascii=False, default=str)
            text = f"{text}\n[Oldingi function calllar: {serialized[:6000]}]".strip()
        if text:
            result.append({"role": "assistant", "content": text})
    return result
