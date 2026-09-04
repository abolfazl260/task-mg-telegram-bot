"""Compatibility helpers for raw Rich Message Bot API responses."""

from typing import Any


def _message_id(value: Any):
    if isinstance(value, dict):
        if value.get("message_id"):
            return value["message_id"]
        result = value.get("result")
        if isinstance(result, dict) and result.get("message_id"):
            return result["message_id"]
        return None
    return getattr(value, "message_id", None)


def install_create_task_rich_response_compat(flow_module) -> None:
    """Make the create flow handle both PTB Message and raw dict responses."""
    if getattr(flow_module, "_rich_response_compat_installed", False):
        return
    flow_module._rich_response_compat_installed = True

    async def send_rich(context, message, html):
        sent = await context.bot._post("sendRichMessage", data={
            "chat_id": message.chat_id,
            "rich_message": {"html": html, "is_rtl": True},
        })
        message_id = _message_id(sent)
        if not message_id:
            raise RuntimeError(
                f"Telegram did not return a Rich Message id (response type: {type(sent).__name__})"
            )
        context.user_data["create_task_message_id"] = message_id
        return sent

    flow_module._send_rich = send_rich
