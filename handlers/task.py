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
    try:
        if text is None:
            await query.answer()
        else:
            await query.answer(text, show_alert=show_alert)
        return True
    except BadRequest as exc:
        message = str(exc).lower()
        if 'too old' in message or 'invalid' in message or 'query id' in message:
            logger.info('Ignoring stale/invalid callback query id=%s: %s', getattr(query, 'id', ''), exc)
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

async def _comments_markdown(task_id: str) -> str:
    comments = await get_task_comments_async(task_id)
    if not comments:
        return '💬 هنوز کامنتی برای این تسک ثبت نشده است.'
    lines = ['💬 کامنت\u200cها', '']
    for i, comment in enumerate(comments, start=1):
        author = comment.get('author_name') or 'کاربر'
        username = f" (@{comment.get('author_username')})" if comment.get('author_username') else ''
        lines.append(f'{i}. {_comment_type_label(comment)} — {author}{username}')
        lines.append(f"   🕐 {comment.get('created_at') or '—'}")
        lines.append(f'   {_comment_summary(comment)}')
        lines.append('')
    return '\n'.join(lines).strip()

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
    text = (update.message.text or '').strip()
    if not _is_bare_task_id(text):
        return False
    task = await get_task_by_id_async(text)
    if not task or not await _can_view_task(update.effective_user.id, task):
        await update.message.reply_text('تسکی با این کد برای شما پیدا نشد.')
        return True
    kb = task_action_keyboard(task.get('id', ''), task.get('status', 'pending'), context.bot_data.get('bot_config')) if await user_can_modify_task_async(update.effective_user.id, task) else _task_details_keyboard(task.get('id', ''))
    await update.message.reply_text(await format_task_card(task), reply_markup=kb, parse_mode='Markdown')
    return True

async def _finalize_task(user_id, task):
    return await create_task_async(user_id=user_id, title=task['title'], priority=task['priority'], deadline=task.get('deadline', ''), category=task.get('category', ''), tags=task.get('tags', ''), description=task.get('description', ''), team_id=task.get('team_id', '') or '', assignee=task.get('assignee'))

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_task'] = {}
    context.user_data['step'] = 'title'
    await update.message.reply_text('📝 عنوان تسک را وارد کنید:')

async def save_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_custom_bot_text(update, context): return
    if await handle_habit_text(update, context): return
    if await handle_team_text(update, context): return
    if await handle_import_document(update, context): return
    if await handle_import_text(update, context): return
    if await handle_change_assignment_search_text(update, context): return
    if await handle_assignment_search_text(update, context): return
    if await handle_comment_input(update, context): return
    if await handle_search_text(update, context): return
    if await show_task_by_id_if_matches(update, context): return
    if 'step' not in context.user_data: return
    step = context.user_data['step']; text = update.message.text; task = context.user_data.get('new_task')
    if task is None and step not in ('search_query', 'import_bulk', 'team_create_name', 'team_join_code'): return
    if step == 'title':
        task['title'] = text; context.user_data['step'] = 'priority'; await update.message.reply_text('🎯 اولویت را انتخاب کنید:', reply_markup=priority_keyboard()); return
    if step == 'deadline_custom':
        parsed = parse_deadline_input(text)
        if not parsed: await update.message.reply_text('⚠️ تاریخ نامعتبر است.\nمثال میلادی: `2026-08-20`\nمثال شمسی: `1405-05-29`', parse_mode='Markdown'); return
        task['deadline'] = parsed; context.user_data['step'] = 'category'; await _ask_category(update.message, context, update.effective_user.id); return
    if step == 'category': task['category'] = text; await _ask_tags(update.message, context); return
    if step == 'tags': task['tags'] = text; await _ask_description(update.message, context); return
    if step == 'description': task['description'] = text; await _ask_assignment(update, context)

async def priority_selected(update, context):
    query = update.callback_query; await query.answer(); priority = query.data.replace('priority_', '')
    if priority not in PRIORITY_LABEL: await query.message.reply_text('⚠️ لطفاً یکی از سه اولویت بالا، متوسط یا پایین را انتخاب کنید.'); return
    context.user_data.setdefault('new_task', {})['priority'] = priority
    await query.message.reply_text('📅 زمان انجام را انتخاب کنید:\n(می\u200cتوانید بدون زمان\u200cبندی ثبت کنید)', reply_markup=deadline_keyboard())

async def deadline_selected(update, context):
    query = update.callback_query; await query.answer(); value = query.data.replace('deadline_', '')
    if value == 'custom': context.user_data['step'] = 'deadline_custom'; await query.message.reply_text('📅 تاریخ دقیق را وارد کنید:\n• میلادی: `2026-08-20`\n• شمسی: `1405-05-29`', parse_mode='Markdown'); return
    if value == 'none': context.user_data['new_task']['deadline'] = ''; context.user_data['step'] = 'category'; await _ask_category(query.message, context, update.effective_user.id); return
    days = int(value); deadline = datetime.now() + timedelta(days=days); context.user_data['new_task']['deadline'] = deadline.strftime('%Y-%m-%d'); context.user_data['step'] = 'category'; await _ask_category(query.message, context, update.effective_user.id)

async def skip_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await habit_skip(update, context): return
    step = context.user_data.get('step'); task = context.user_data.get('new_task')
    if not task: return
    if step == 'category': task['category'] = ''; await _ask_tags(update.message, context); return
    if step == 'tags': task['tags'] = ''; await _ask_description(update.message, context); return
    if step == 'description': task['description'] = ''; await _ask_assignment(update, context)

async def optional_field_callback(update, context):
    query = update.callback_query; await query.answer(); data = query.data; task = context.user_data.get('new_task')
    if not task: await query.message.reply_text('فرایند ایجاد تسک فعالی پیدا نشد.'); return
    if data == 'category_skip': task['category'] = ''; await _ask_tags(query.message, context); return
    if data.startswith('category_pick_'):
        selected = data.replace('category_pick_', '', 1); categories = [(t.get('category') or '').strip() for t in await get_active_tasks_async(update.effective_user.id) if (t.get('category') or '').strip()]; matched = next((c for c in categories if c[:40] == selected), selected); task['category'] = matched; await _ask_tags(query.message, context); return
    if data == 'tags_skip': task['tags'] = ''; await _ask_description(query.message, context); return
    if data == 'description_skip': task['description'] = ''; await _ask_assignment(update, context); return

def sort_tasks(tasks, key: str='deadline'):
    if key == 'priority': return sorted(tasks, key=lambda x: PRIORITY_ORDER.get(x.get('priority'), 9))
    if key == 'created': return sorted(tasks, key=lambda x: x.get('created_at') or '', reverse=True)
    return sorted(tasks, key=lambda x: x.get('deadline') or '9999-99-99')

def build_detail_table(tasks, start_index=1):
    text = '# 📋 فهرست اقدامات\n\n| شماره | جزئیات |\n|---|---|\n'
    for index, task in enumerate(tasks, start=start_index):
        priority = {'high': '🔴', 'medium': '🟠', 'low': '🟢'}.get(task.get('priority'), '🟢'); status = {'pending': '⏳', 'in_progress': '🚀', 'done': '✅', 'cancelled': '❌'}.get(task.get('status'), '⏳'); team_mark = ' 👥' if task.get('team_id') else ''; text += f"| {index} | {priority} {task.get('title', '-')} {status}{team_mark} |\n"
    text += '\n\n📌 راهنما\n\n🔴 بالا\n🟠 متوسط\n🟢 پایین\n\n⏳ در انتظار\n🚀 در حال انجام\n✅ انجام شده\n❌ لغو شده\n👥 تیمی\n'; return text

def _assignee_label(task):
    name = (task.get('assignee_name') or '').strip(); username = (task.get('assignee_username') or '').strip(); assignee_id = (task.get('assignee_id') or '').strip()
    if name: return name
    if username: return f"@{username.lstrip('@')}"
    if assignee_id: return f'ID:{assignee_id}'
    return 'بدون مسئول'

def build_full_report(tasks):
    table = '# 📊 گزارش پیگیری اقدامات\n\n| # | موضوع | مسئول | دسته | تگ | اولویت | میلادی | شمسی | زمان | وضعیت | توضیح |\n|---|---|---|---|---|---|---|---|---|---|---|\n'
    for index, task in enumerate(tasks, start=1):
        priority = {'high': '🔴', 'medium': '🟠', 'low': '🟢'}.get(task.get('priority'), '🟢'); deadline = task.get('deadline') or '-'
        try:
            deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date(); diff = (deadline_date - datetime.now().date()).days; remaining = f'🔻{abs(diff)}' if diff < 0 else ('⏰' if diff == 0 else (f'⚠️{diff}' if diff <= 3 else f'🕒{diff}')); jalali_date = jdatetime.date.fromgregorian(date=deadline_date).strftime('%Y/%m/%d')
        except Exception: remaining = '-'; jalali_date = '-'
        status = {'pending': '⏳', 'in_progress': '🚀', 'done': '✅', 'cancelled': '❌'}.get(task.get('status'), '-'); desc = (task.get('description') or '-').replace('\n', ' ')[:40]
        table += f"| {index} | {task.get('title', '-')} | {_assignee_label(task)} | {task.get('category') or '-'} | {task.get('tags') or '-'} | {priority} | {deadline} | {jalali_date} | {remaining} | {status} | {desc} |\n"
    return table

async def format_task_card(task: dict) -> str:
    title = task.get('title', '-'); task_id = task.get('id', ''); priority = PRIORITY_LABEL.get(task.get('priority'), task.get('priority', '-')); status = STATUS_LABEL.get(task.get('status'), task.get('status', '-')); deadline = task.get('deadline') or 'بدون ددلاین'; category = task.get('category') or '—'; tags = task.get('tags') or '—'; created = task.get('created_at') or '—'; description = task.get('description') or '—'; team_id = task.get('team_id') or ''; jalali = '—'; remaining = '—'
    if task.get('deadline'):
        try:
            deadline_date = datetime.strptime(task['deadline'], '%Y-%m-%d').date(); jalali = jdatetime.date.fromgregorian(date=deadline_date).strftime('%Y/%m/%d'); diff = (deadline_date - datetime.now().date()).days; remaining = f'🔻 {abs(diff)} روز گذشته' if diff < 0 else ('⏰ امروز' if diff == 0 else (f'⚠️ {diff} روز مانده' if diff <= 3 else f'🕒 {diff} روز مانده'))
        except Exception: pass
    team_line = f'👥 تیم: `{team_id}`\n' if team_id else ''; assignee = task.get('assignee_name') or '❌ تعیین نشده'; comments_count = len(await get_task_comments_async(task_id)) if task_id else 0
    return f'**{title}**\n\n🆔 `{task_id}`\n{team_line}🎯 اولویت: {priority}\n📌 وضعیت: {status}\n👤 مسئول: 🖼 {assignee}\n📅 مهلت: {deadline}\n🗓️ شمسی: {jalali}\n⏳ باقی\u200cمانده: {remaining}\n📂 دسته: {category}\n🏷 تگ: {tags}\n📄 توضیح: {description}\n🕐 ثبت: {created}\n💬 کامنت\u200cها: {comments_count}'

async def _render_task_list(update, context, sort_key='deadline', edit=False):
    message = update.effective_message; tasks = await get_active_tasks_async(update.effective_user.id)
    if not tasks: await message.reply_text('🎉 تسک فعال ندارید'); return
    tasks = sort_tasks(tasks, sort_key); context.user_data['tasks_sort'] = sort_key; high_count = medium_count = low_count = 0
    for task in tasks:
        if task.get('priority') == 'high': high_count += 1
        elif task.get('priority') == 'medium': medium_count += 1
        else: low_count += 1
    sort_label = {'deadline': 'ددلاین', 'priority': 'اولویت', 'created': 'تاریخ ایجاد'}.get(sort_key, sort_key)
    await message.reply_text(f'\n# 🚦 وضعیت اولویت\u200cها\n\n🔴 بالا — {high_count}\n🟠 متوسط — {medium_count}\n🟢 پایین — {low_count}\n\n🔀 مرتب\u200cسازی فعلی: **{sort_label}**', parse_mode='Markdown')
    first_page = tasks[:PAGE_SIZE]; text = build_detail_table(first_page); keyboard = [[InlineKeyboardButton('📅 ددلاین', callback_data='sort_deadline'), InlineKeyboardButton('🎯 اولویت', callback_data='sort_priority'), InlineKeyboardButton('🕐 ایجاد', callback_data='sort_created')]]
    if len(tasks) > PAGE_SIZE: keyboard.append([InlineKeyboardButton('➡️ صفحه بعد', callback_data='detail_page_2')])
    keyboard.append([InlineKeyboardButton('📥 خروجی Excel', callback_data='download_csv')]); await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard)); table = build_full_report(tasks); await context.bot._post('sendRichMessage', data={'chat_id': update.effective_chat.id, 'rich_message': {'markdown': table}}); await message.reply_text('⬇️ جزئیات کامل هر تسک + دکمه\u200cهای تغییر وضعیت:')
    for task in first_page:
        can_mod = await user_can_modify_task_async(update.effective_user.id, task); kb = task_action_keyboard(task.get('id', ''), task.get('status', 'pending'), context.bot_data.get('bot_config')) if can_mod else _task_details_keyboard(task.get('id', '')); await message.reply_text(await format_task_card(task), reply_markup=kb, parse_mode='Markdown')

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sort_key = context.user_data.get('tasks_sort', 'deadline'); await _render_task_list(update, context, sort_key=sort_key)

async def sort_tasks_callback(update, context):
    query = update.callback_query; await query.answer(); key = query.data.replace('sort_', ''); key = key if key in ('deadline', 'priority', 'created') else 'deadline'; await _render_task_list(update, context, sort_key=key)

async def download_csv(update, context):
    query = update.callback_query; await query.answer(); buffer, count = build_csv_bytes(update.effective_user.id)
    if count == 0: await query.message.reply_text('🎉 تسک فعالی برای دانلود ندارید'); return
    await query.message.reply_document(document=buffer, filename='tasks.csv', caption=f'📥 {count} تسک فعال (فرمت CSV)')

async def detail_page(update, context):
    query = update.callback_query; await query.answer()
    try: page = int(query.data.replace('detail_page_', ''))
    except ValueError: page = 1
    tasks = await get_active_tasks_async(update.effective_user.id)
    if not tasks: await query.message.reply_text('🎉 تسک فعال ندارید'); return
    sort_key = context.user_data.get('tasks_sort', 'deadline'); tasks = sort_tasks(tasks, sort_key); total_pages = max(1, -(-len(tasks) // PAGE_SIZE)); page = min(page, total_pages); start_index = (page - 1) * PAGE_SIZE + 1; start = (page - 1) * PAGE_SIZE; end = start + PAGE_SIZE; page_tasks = tasks[start:end]; text = build_detail_table(page_tasks, start_index=start_index) + f'\n\n📄 صفحه {page} از {total_pages}'; keyboard = []; nav = []
    if page > 1: nav.append(InlineKeyboardButton('⬅️ قبلی', callback_data=f'detail_page_{page - 1}'))
    if page < total_pages: nav.append(InlineKeyboardButton('➡️ بعدی', callback_data=f'detail_page_{page + 1}'))
    if nav: keyboard.append(nav)
    keyboard.append([InlineKeyboardButton('📥 خروجی Excel', callback_data='download_csv')]); await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def _task_details_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton('💬 افزودن کامنت', callback_data=f'comment_add_{task_id}')], [InlineKeyboardButton('📜 تاریخچه', callback_data=f'task_history_{task_id}')]])

async def task_details_callback(update, context):
    query = update.callback_query; await query.answer(); data = query.data; task_id = data.replace('task_details_', '', 1).replace('task_history_', '', 1); task = await get_task_by_id_async(task_id)
    if not task or not await _can_view_task(update.effective_user.id, task): await query.message.reply_text('تسک پیدا نشد یا دسترسی ندارید.'); return
    text = f'{await format_task_card(task)}\n\n{_history_text(task)}\n\n{await _comments_markdown(task_id)}'
    try: await context.bot._post('sendRichMessage', data={'chat_id': query.message.chat_id, 'rich_message': {'markdown': text}})
    except Exception: await query.message.reply_text(text, parse_mode='Markdown')
    await _send_comment_attachments(query.message, task_id); await query.message.reply_text('برای ثبت کامنت جدید دکمه زیر را بزنید:', reply_markup=_task_details_keyboard(task_id))

async def comment_callback(update, context):
    query = update.callback_query; await query.answer(); task_id = query.data.replace('comment_add_', '', 1); task = await get_task_by_id_async(task_id)
    if not task or not await _can_view_task(update.effective_user.id, task): await query.message.reply_text('تسک پیدا نشد یا دسترسی ندارید.'); return
    context.user_data['comment_task_id'] = task_id; context.user_data['step'] = 'task_comment'; await query.message.reply_text('💬 کامنت خود را ارسال کنید؛ متن، عکس، صدا، فایل یا هر پیام تلگرامی پشتیبانی\u200cشده قابل ثبت است.')

async def handle_comment_input(update, context):
    if context.user_data.get('step') != 'task_comment': return False
    task_id = context.user_data.get('comment_task_id'); task = await get_task_by_id_async(task_id)
    if not task or not await _can_view_task(update.effective_user.id, task): context.user_data.pop('comment_task_id', None); context.user_data.pop('step', None); await update.effective_message.reply_text('تسک پیدا نشد یا دسترسی ندارید.'); return True
    content = _extract_comment_content(update.effective_message)
    if not content: await update.effective_message.reply_text('این نوع پیام برای کامنت پشتیبانی نشد. لطفاً متن، عکس، صدا یا فایل بفرستید.'); return True
    user = update.effective_user; ok = await add_task_comment_async(task_id, {'id': user.id, 'full_name': user.full_name, 'username': user.username or ''}, content); context.user_data.pop('comment_task_id', None); context.user_data.pop('step', None); await update.effective_message.reply_text('✅ کامنت ثبت شد.' if ok else '❌ خطا در ثبت کامنت.'); return True
STATUS_LABELS = {'pending': '⏳ در انتظار', 'in_progress': '🚀 در حال انجام', 'done': '✅ انجام شده', 'cancelled': '❌ لغو شده'}

async def _handle_status_change(update, context, new_status: str):
    query = update.callback_query
    await _safe_query_answer(query)
    prefix = query.data.split('_')[0]
    task_id = query.data.replace(f'{prefix}_', '', 1)
    task = await get_task_by_id_async(task_id)
    if not task:
        await query.message.reply_text('⚠️ این تسک پیدا نشد.')
        return
    if not await user_can_modify_task_async(update.effective_user.id, task):
        return
    success = await change_task_status_async(task_id, new_status)
    if not success:
        await query.message.reply_text('❌ خطا در تغییر وضعیت تسک.')
        return
    task['status'] = new_status
    if new_status == 'done':
        task['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    label = STATUS_LABELS.get(new_status, new_status)
    try:
        await query.edit_message_text(await format_task_card(task), parse_mode='Markdown')
    except BadRequest as exc:
        if 'message is not modified' not in str(exc).lower():
            raise
    logger.info('task_status_changed task_id=%s user_id=%s new_status=%s', task_id, update.effective_user.id, new_status)
    await query.message.reply_text(f"وضعیت تسک «{task.get('title', '-')}» به {label} تغییر کرد.")

async def start_task(update, context): await _handle_status_change(update, context, 'in_progress')
async def done_task(update, context): await _handle_status_change(update, context, 'done')
async def cancel_task(update, context): await _handle_status_change(update, context, 'cancelled')
async def pending_task(update, context): await _handle_status_change(update, context, 'pending')

