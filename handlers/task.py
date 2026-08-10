from datetime import datetime, timedelta
import logging
import jdatetime
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from services.task_service import create_task_async, get_active_tasks_async, get_task_by_id_async, change_task_status_async, user_can_modify_task_async, assign_task_async, get_unassigned_tasks_async, add_task_comment_async, get_task_comments_async
from services.csv_export import build_csv_bytes
from services.team_service import aget_user_teams, aget_team_members, member_display
from utils.keyboard import priority_keyboard, deadline_keyboard, task_action_keyboard
from utils.date_parse import parse_deadline_input
from handlers.search_share import handle_search_text
from handlers.import_bulk import handle_import_document, handle_import_text
from handlers.team import handle_team_text
from handlers.habits import handle_habit_text, habit_skip
from handlers.custom_bot import handle_custom_bot_text
logger = logging.getLogger(__name__)
PAGE_SIZE = 10
PRIORITY_LABEL = {'high': '🔴 بالا', 'medium': '🟠 متوسط', 'low': '🟢 پایین'}
STATUS_LABEL = {'pending': '⏳ در انتظار', 'in_progress': '🚀 در حال انجام', 'done': '✅ انجام شده', 'cancelled': '❌ لغو شده'}
PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

async def _safe_query_answer(query, text=None, show_alert=False):
    """Acknowledge a Telegram callback without crashing on stale/duplicate queries."""
    try:
        if text is None:
            await query.answer()
        else:
            await query.answer(text, show_alert=show_alert)
        return True
    except BadRequest as exc:
        message = str(exc).lower()
        if "too old" in message or "invalid" in message or "query id" in message:
            logger.info("Ignoring stale/invalid callback query id=%s: %s", getattr(query, "id", ""), exc)
            return False
        raise


def _skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton('⏭ رد کردن', callback_data=callback_data)]])

async def _category_keyboard(user_id) -> InlineKeyboardMarkup:
    categories = []
    seen = set()
    for task in await get_active_tasks_async(user_id):
        category = (task.get('category') or '').strip()
        key = category.lower()
        if category and key not in seen:
            seen.add(key)
            categories.append(category)
    rows = [[InlineKeyboardButton(f'📂 {cat}', callback_data=f'category_pick_{cat[:40]}')] for cat in categories[:10]]
    rows.append([InlineKeyboardButton('⏭ رد کردن', callback_data='category_skip')])
    return InlineKeyboardMarkup(rows)

async def _ask_category(message, context, user_id):
    await message.reply_text('📂 دسته\u200cبندی را انتخاب کنید یا نام دسته\u200cبندی جدید را همین\u200cجا ارسال کنید تا ساخته شود.\nاگر دسته\u200cبندی نمی\u200cخواهید، دکمه «رد کردن» را بزنید:', reply_markup=await _category_keyboard(user_id))

async def _ask_tags(message, context):
    context.user_data['step'] = 'tags'
    await message.reply_text('🏷 تگ را وارد کنید یا دکمه «رد کردن» را بزنید:', reply_markup=_skip_keyboard('tags_skip'))

async def _ask_description(message, context):
    context.user_data['step'] = 'description'
    await message.reply_text('📄 توضیح / یادداشت را وارد کنید یا دکمه «رد کردن» را بزنید:\n(اختیاری)', reply_markup=_skip_keyboard('description_skip'))

# ...
