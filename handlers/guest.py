"""Guest Mode support for creating quick tasks from any Telegram chat.

python-telegram-bot 22.0 predates Telegram Bot API 10.0 Guest Mode,
so guest updates are currently exposed as unknown ``Update.api_kwargs``.
This module reads that raw payload and answers it through the raw Bot API
``answerGuestQuery`` method.
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from services.task_service import create_task
from utils.date_parse import parse_deadline_input

logger = logging.getLogger(__name__)

_ADD_WORDS = ("add", "task", "todo", "تسک", "وظیفه", "کار", "ثبت", "ایجاد")
_PRIORITY_WORDS = {
    "high": ("high", "بالا", "فوری", "مهم", "🔴"),
    "medium": ("medium", "متوسط", "عادی", "🟠"),
    "low": ("low", "پایین", "کم", "🟢"),
}


def _guest_message(update: Update) -> dict | None:
    return (update.api_kwargs or {}).get("guest_message")


def _user_label(user: dict | None) -> str:
    if not user:
        return "کاربر مهمان"
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    username = (user.get("username") or "").strip()
    return (first + (" " + last if last else "")).strip() or (f"@{username}" if username else "کاربر مهمان")


def _extract_title(text: str, bot_username: str = "") -> str:
    title = (text or "").strip()
    if bot_username:
        title = re.sub(rf"@{re.escape(bot_username)}\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"^/(add|task|todo)(?:@\w+)?\b", " ", title, flags=re.IGNORECASE).strip()
    for word in _ADD_WORDS:
        title = re.sub(rf"^(?:{re.escape(word)})[:：\-\s]+", "", title, flags=re.IGNORECASE).strip()
    return title[:240]


def _extract_priority(text: str) -> str:
    lowered = (text or "").lower()
    for priority, words in _PRIORITY_WORDS.items():
        if any(word.lower() in lowered for word in words):
            return priority
    return "medium"


def _extract_deadline(text: str) -> str:
    for token in re.findall(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", text or ""):
        parsed = parse_deadline_input(token.replace("/", "-"))
        if parsed:
            return parsed
    return ""


def _article_result(title: str, text: str) -> dict:
    return {
        "type": "article",
        "id": "guest-task-created",
        "title": title[:64],
        "input_message_content": {
            "message_text": text,
            "parse_mode": ParseMode.MARKDOWN,
        },
    }


async def _answer_guest_query(context: ContextTypes.DEFAULT_TYPE, guest_query_id: str, text: str) -> None:
    await context.bot._post(
        "answerGuestQuery",
        data={
            "guest_query_id": guest_query_id,
            "result": _article_result("ثبت تسک", text),
        },
    )


async def handle_guest_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create one-shot tasks from Guest Mode messages.

    Usage in any supported chat after Guest Mode is enabled in BotFather:
    ``@YourBot add Buy server credits 2026-08-20 فوری``.
    """

    guest = _guest_message(update)
    if not guest:
        return

    guest_query_id = guest.get("guest_query_id")
    caller = guest.get("from") or guest.get("guest_bot_caller_user") or {}
    user_id = caller.get("id")
    raw_text = guest.get("text") or guest.get("caption") or ""
    chat = guest.get("chat") or {}
    chat_title = (chat.get("title") or chat.get("username") or "Guest Mode").strip()

    if not guest_query_id:
        logger.warning("guest_update_without_query_id update_id=%s", update.update_id)
        return
    if not user_id:
        await _answer_guest_query(context, guest_query_id, "⚠️ کاربر ارسال‌کننده قابل تشخیص نیست؛ تسک ثبت نشد.")
        return

    bot_username = (getattr(context.bot, "username", None) or "").strip()
    title = _extract_title(raw_text, bot_username)
    if not title:
        await _answer_guest_query(
            context,
            guest_query_id,
            "برای ثبت تسک، بات را همراه عنوان صدا بزنید؛ مثل:\n`@YourBot add پیگیری قرارداد 2026-08-20 فوری`",
        )
        return

    priority = _extract_priority(raw_text)
    deadline = _extract_deadline(raw_text)
    task_id = create_task(
        user_id=user_id,
        title=title,
        priority=priority,
        deadline=deadline,
        category=f"Guest: {chat_title}"[:60],
        tags="guest",
        description=f"ساخته‌شده با Guest Mode توسط {_user_label(caller)} از چت «{chat_title}»",
    )

    logger.info("guest_task_created task_id=%s user_id=%s chat_id=%s", task_id, user_id, chat.get("id", ""))
    await _answer_guest_query(
        context,
        guest_query_id,
        "✅ تسک مهمان ثبت شد\n\n"
        f"🆔 `{task_id}`\n"
        f"📌 {title}\n"
        f"📂 Guest: {chat_title}\n"
        f"📅 {deadline or 'بدون ددلاین'}",
    )
