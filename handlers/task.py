from datetime import datetime, timedelta
import logging
import jdatetime
from telegram import Update
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

def _is_bare_task_id(text: str) -> bool:
    value = (text or '').strip()
    return len(value) == 8 and value.isalnum()

async def _can_view_task(user_id, task: dict) -> bool:
    return any((t.get('id') == task.get('id') for t in await get_active_tasks_async(user_id))) or await user_can_modify_task_async(user_id, task)

def _comment_type_label(comment: dict) -> str:
    return {'text': '💬 متن', 'photo': '🖼 عکس', 'voice': '🎙 صدا', 'audio': '🎧 صوت', 'document': '📎 فایل', 'video': '🎬 ویدیو', 'sticker': '🏷 استیکر', 'animation': '🎞 گیف', 'contact': '👤 مخاطب', 'location': '📍 موقعیت'}.get(comment.get('type'), '📎 مورد')

def _comment_summary(comment: dict) -> str:
    body = comment.get('text') or comment.get('caption') or comment.get('file_name') or comment.get('emoji') or 'بدون متن'
    return str(body).replace('\n', ' ')[:160]

async def _send_comment_attachments(message, task_id: str):
    for comment in await get_task_comments_async(task_id):
        caption = f"{_comment_type_label(comment)} — {comment.get('author_name') or 'کاربر'}\n🕐 {comment.get('created_at') or '—'}\n{comment.get('caption') or comment.get('text') or comment.get('file_name') or ''}"[:1024]
        file_id = comment.get('file_id')
        ctype = comment.get('type')
        try:
            if ctype == 'photo' and file_id:
                await message.reply_photo(file_id, caption=caption)
            elif ctype == 'voice' and file_id:
                await message.reply_voice(file_id, caption=caption)
            elif ctype == 'audio' and file_id:
                await message.reply_audio(file_id, caption=caption)
            elif ctype == 'video' and file_id:
                await message.reply_video(file_id, caption=caption)
            elif ctype == 'animation' and file_id:
                await message.reply_animation(file_id, caption=caption)
            elif ctype == 'sticker' and file_id:
                await message.reply_sticker(file_id)
            elif ctype == 'document' and file_id:
                await message.reply_document(file_id, caption=caption)
        except Exception:
            continue

def _extract_comment_content(message) -> dict | None:
    if message.text:
        return {'type': 'text', 'text': message.text}
    if message.photo:
        return {'type': 'photo', 'file_id': message.photo[-1].file_id, 'caption': message.caption or ''}
    if message.voice:
        return {'type': 'voice', 'file_id': message.voice.file_id, 'caption': message.caption or ''}
    if message.audio:
        return {'type': 'audio', 'file_id': message.audio.file_id, 'file_name': message.audio.file_name or '', 'caption': message.caption or ''}
    if message.document:
        return {'type': 'document', 'file_id': message.document.file_id, 'file_name': message.document.file_name or '', 'caption': message.caption or ''}
    if message.video:
        return {'type': 'video', 'file_id': message.video.file_id, 'file_name': message.video.file_name or '', 'caption': message.caption or ''}
    if message.sticker:
        return {'type': 'sticker', 'file_id': message.sticker.file_id, 'emoji': message.sticker.emoji or ''}
    if message.animation:
        return {'type': 'animation', 'file_id': message.animation.file_id, 'file_name': message.animation.file_name or '', 'caption': message.caption or ''}
    if message.contact:
        return {'type': 'contact', 'text': message.contact.full_name or message.contact.phone_number or 'مخاطب'}
    if message.location:
        return {'type': 'location', 'text': f'{message.location.latitude},{message.location.longitude}'}
    return None

async def show_task_by_id_if_matches(update, context) -> bool:
    text = (update.effective_message.text or '').strip()
    if not _is_bare_task_id(text):
        return False
    task = await get_task_by_id_async(text)
    if not task or not await _can_view_task(update.effective_user.id, task):
        await update.effective_message.reply_text('تسکی با این کد برای شما پیدا نشد.')
        return True
    kb = task_action_keyboard(task.get('id', ''), task.get('status', 'pending'), context.bot_data.get('bot_config')) if await user_can_modify_task_async(update.effective_user.id, task) else _task_details_keyboard(task.get('id', ''))
    await update.effective_message.reply_text(await format_task_card(task), reply_markup=kb, parse_mode='Markdown')
    return True

async def _finalize_task(user_id, task):
    return await create_task_async(user_id=user_id, title=task['title'], priority=task['priority'], deadline=task.get('deadline', ''), category=task.get('category', ''), tags=task.get('tags', ''), description=task.get('description', ''), team_id=task.get('team_id', '') or '', assignee=task.get('assignee'))

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_task'] = {}
    context.user_data['step'] = 'title'
    message = update.effective_message
    if message is None:
        await update.callback_query.message.reply_text('📝 عنوان تسک را وارد کنید:')
        return
    await message.reply_text('📝 عنوان تسک را وارد کنید:')

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_custom_bot_text(update, context):
        return
    if await handle_habit_text(update, context):
        return
    if await handle_team_text(update, context):
        return
    if await handle_import_document(update, context):
        return
    if await handle_import_text(update, context):
        return
    if await handle_change_assignment_search_text(update, context):
        return
    if await handle_assignment_search_text(update, context):
        return
    if await handle_comment_input(update, context):
        return
    if await handle_search_text(update, context):
        return
    if await show_task_by_id_if_matches(update, context):
        return
    if 'step' not in context.user_data:
        return
    step = context.user_data['step']
    text = update.effective_message.text
    task = context.user_data.get('new_task')
    if task is None and step not in ('search_query', 'import_bulk', 'team_create_name', 'team_join_code'):
        return
    if step == 'title':
        task['title'] = text
        context.user_data['step'] = 'priority'
        await update.effective_message.reply_text('🎯 اولویت را انتخاب کنید:', reply_markup=priority_keyboard())
        return
