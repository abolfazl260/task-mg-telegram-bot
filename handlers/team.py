"""Team / shared space commands and callbacks.

Share flow (category-based):
  1) User chooses which category/space to share
  2) User chooses role (editor / viewer)
  3) Bot sends ready-to-forward invite with correct deep link
"""
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import BOT_USERNAME
from services.team_service import create_team, join_team_by_code, find_team_by_code, aget_user_teams, get_team, aget_team_members, leave_team, regenerate_codes, role_label, member_display, ROLE_OWNER, ROLE_EDITOR, ROLE_VIEWER, can_edit
from services.task_service import get_team_tasks, get_all_user_tasks, link_user_category_to_team

def _e(value) -> str:
    """HTML-escape dynamic text for Telegram HTML parse_mode."""
    return html.escape(str(value if value is not None else ''))

async def _bot_username(context) -> str:
    try:
        if context.bot.username:
            return context.bot.username
        info = await context.bot.get_me()
        if info and info.username:
            return info.username
    except Exception:
        pass
    return BOT_USERNAME or 'TaskManagerpersian_Bot'

def _deep_link(bot_username: str, code: str) -> str:
    return f'https://t.me/{bot_username}?start=join_{code}'

def _invite_message(team: dict, role: str, bot_username: str) -> str:
    code = team.get('editor_code') if role == ROLE_EDITOR else team.get('viewer_code')
    link = _deep_link(bot_username, code)
    name = _e(team.get('name'))
    tid = _e(team.get('team_id'))
    code_e = _e(code)
    role_fa = '✏️ ویرایشگر — می\u200cتواند تسک بسازد و وضعیت را عوض کند' if role == ROLE_EDITOR else '👁 مشاهده\u200cکننده — فقط مشاهده تسک\u200cها'
    return f'📨 دعوت به دسته\u200cبندی مشترک\n\n📂 دسته\u200cبندی در حال اشتراک: <b>{name}</b>\n🆔 <code>{tid}</code>\nنقش این دعوت: {role_fa}\n\nعضویت با یک کلیک:\n{link}\n\nیا در ربات بفرست:\n/team join {code_e}\n\n—\nفقط همین دسته\u200cبندی («{name}») به اشتراک گذاشته می\u200cشود.'

def _codes_text(team: dict, bot_username: str) -> str:
    ed = team.get('editor_code') or ''
    vw = team.get('viewer_code') or ''
    name = _e(team.get('name'))
    tid = _e(team.get('team_id'))
    return f'📂 دسته\u200cبندی: <b>{name}</b>\n🆔 <code>{tid}</code>\n\n✏️ لینک ویرایشگر:\n{_deep_link(bot_username, ed)}\nکد: <code>{_e(ed)}</code>\n\n👁 لینک مشاهده:\n{_deep_link(bot_username, vw)}\nکد: <code>{_e(vw)}</code>\n\n⚠️ هر لینک نقش جدا دارد.'

def _format_members_list(team_name: str, members: list) -> str:
    owners = [m for m in members if m.get('role') == ROLE_OWNER]
    editors = [m for m in members if m.get('role') == ROLE_EDITOR]
    viewers = [m for m in members if m.get('role') == ROLE_VIEWER]
    lines = [f'👥 اعضای «{_e(team_name)}»\n', f'تعداد کل: <b>{len(members)}</b> نفر\n']

    def section(title, items):
        if not items:
            return
        lines.append(f'\n{title} ({len(items)}):')
        for i, m in enumerate(items, start=1):
            lines.append(f'  {i}. {_e(member_display(m))}')
            lines.append(f"     🆔 <code>{_e(m.get('user_id'))}</code> · {_e(m.get('joined_at') or '—')}")
    section('👑 مالک', owners)
    section('✏️ ویرایشگر', editors)
    section('👁 مشاهده\u200cکننده', viewers)
    return '\n'.join(lines)

def _user_categories(user_id) -> list:
    cats = []
    seen = set()
    for t in get_all_user_tasks(user_id):
        if (t.get('team_id') or '').strip():
            continue
        cat = (t.get('category') or '').strip()
        if not cat:
            continue
        key = cat.lower()
        if key not in seen:
            seen.add(key)
            cats.append(cat)
    return cats

def _sync_category_tasks(user_id, team: dict) -> int:
    """Link personal tasks of same category name into this team."""
    if not team:
        return 0
    name = (team.get('name') or '').strip()
    team_id = team.get('team_id')
    if not name or not team_id:
        return 0
    return link_user_category_to_team(user_id, name, team_id)

async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    user = update.effective_user
    user_id = user.id
    bot_user = await _bot_username(context)
    if not args:
        await _show_team_menu(update, context)
        return
    action = args[0].lower()
    if action in ('create', 'new', 'ساخت'):
        name = ' '.join(args[1:]).strip()
        if not name:
            context.user_data['step'] = 'team_create_name'
            await update.message.reply_text('نام دسته\u200cبندی مشترک را وارد کنید:')
            return
        team = create_team(user_id, name, user=user)
        n = _sync_category_tasks(user_id, team)
        extra = f'\n🔗 {n} تسک شخصی این دسته به فضای مشترک وصل شد.' if n else ''
        await update.message.reply_text(f'✅ دسته\u200cبندی مشترک ساخته شد{extra}\n\n' + _codes_text(team, bot_user), parse_mode='HTML', reply_markup=_share_role_keyboard(team['team_id']))
        return
    if action in ('join', 'عضویت'):
        if len(args) < 2:
            context.user_data['step'] = 'team_join_code'
            await update.message.reply_text('کد دعوت یا لینک را بفرست:\nمثال: <code>ABC12X</code>', parse_mode='HTML')
            return
        await _do_join(update, context, _extract_code(' '.join(args[1:])))
        return
    if action in ('share', 'اشتراک', 'اشتراک\u200cگذاری'):
        await _start_share_wizard(update, context)
        return
    if action in ('list', 'لیست', 'my'):
        await _list_teams(update, context)
        return
    if action in ('help', 'راهنما'):
        await update.message.reply_text(_help_text(), parse_mode='HTML')
        return
    await _show_team_menu(update, context)

def _extract_code(raw: str) -> str:
    s = (raw or '').strip()
    if 'start=' in s:
        part = s.split('start=')[-1].split('&')[0].strip()
        for prefix in ('join_', 'team_', 'JOIN_', 'TEAM_'):
            if part.startswith(prefix):
                part = part[len(prefix):]
                break
        return part.strip()
    return s.split()[0] if s else ''

async def _do_join(update, context, code: str):
    user = update.effective_user
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    team_preview, role_preview = find_team_by_code(code)
    if not team_preview:
        if msg:
            await msg.reply_text('⚠️ کد دعوت نامعتبر است.')
        return
    role_fa = '✏️ ویرایشگر' if role_preview == ROLE_EDITOR else '👁 مشاهده\u200cکننده'
    ok, text, team = join_team_by_code(user.id, code, user=user)
    name = (team or team_preview).get('name')
    tid = (team or team_preview).get('team_id')
    linked = 0
    if ok and team and (role_preview in (ROLE_EDITOR, ROLE_OWNER)):
        linked = _sync_category_tasks(user.id, team)
    extra = f'\n🔗 {linked} تسک شخصی هم\u200cنام به این دسته وصل شد.' if linked else ''
    if msg:
        await msg.reply_text(f"{('✅' if ok else '⚠️')} {_e(text)}{extra}\n\n📂 دسته\u200cبندی: <b>{_e(name)}</b>\n🆔 <code>{_e(tid)}</code>\nنقش: {role_fa}", parse_mode='HTML')

def _help_text() -> str:
    return '👥 <b>دسته\u200cبندی مشترک / تیم</b>\n\n<b>اشتراک\u200cگذاری (پیشنهادی):</b>\n۱) /team share یا دکمه 📤 اشتراک دسته\u200cبندی\n۲) انتخاب کن کدام دسته\u200cبندی را می\u200cخواهی به اشتراک بگذاری\n۳) نقش را انتخاب کن (ویرایشگر / مشاهده)\n۴) پیام دعوت را فوروارد کن\n\nوقتی دسته\u200cای را به اشتراک می\u200cگذاری، تسک\u200cهای شخصی همان دسته به\u200cصورت خودکار وارد فضای مشترک می\u200cشوند.\n\n<b>ساخت مستقیم:</b> /team create نام\n<b>عضویت:</b> لینک دعوت یا /team join کد\n'

def _share_role_keyboard(team_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton('📤 دعوت ویرایشگر', callback_data=f'team_share_ed_{team_id}')], [InlineKeyboardButton('📤 دعوت مشاهده\u200cکننده', callback_data=f'team_share_vw_{team_id}')], [InlineKeyboardButton('📂 باز کردن این دسته', callback_data=f'team_open_{team_id}')]])

async def _show_team_menu(update, context):
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('📤 اشتراک\u200cگذاری دسته\u200cبندی', callback_data='team_share_start')], [InlineKeyboardButton('➕ ساخت دسته\u200cبندی مشترک', callback_data='team_create')], [InlineKeyboardButton('🔑 عضویت با کد / لینک', callback_data='team_join')], [InlineKeyboardButton('📋 دسته\u200cهای مشترک من', callback_data='team_list')], [InlineKeyboardButton('❓ راهنما', callback_data='team_help')]])
    text = '👥 دسته\u200cبندی مشترک\n\nبرای اشتراک، اول انتخاب کن کدام دسته را می\u200cخواهی به اشتراک بگذاری.'
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(text, reply_markup=keyboard)

async def _start_share_wizard(update, context):
    user_id = update.effective_user.id
    msg = update.callback_query.message if update.callback_query else update.message
    buttons = []
    for item in await aget_user_teams(user_id):
        t = item['team']
        role = item['role']
        if role not in (ROLE_OWNER, ROLE_EDITOR):
            continue
        buttons.append([InlineKeyboardButton(f"📂 {t['name'][:28]} (مشترک)", callback_data=f"team_sharepick_t_{t['team_id']}")])
    for cat in _user_categories(user_id)[:15]:
        buttons.append([InlineKeyboardButton(f'🏷 {cat[:28]} (از تسک\u200cهای من)', callback_data=f'team_sharepick_c_{cat[:40]}')])
    buttons.append([InlineKeyboardButton('➕ نام جدید برای دسته مشترک', callback_data='team_share_new')])
    buttons.append([InlineKeyboardButton('🔙 انصراف', callback_data='team_menu')])
    if len(buttons) <= 2:
        await msg.reply_text('هنوز دسته\u200cبندی یا فضای مشترکی نداری.\nیک نام جدید بساز یا اول چند تسک با دسته ثبت کن.', reply_markup=InlineKeyboardMarkup(buttons))
        return
    await msg.reply_text('📤 <b>اشتراک\u200cگذاری بر اساس دسته\u200cبندی</b>\n\nکدام دسته\u200cبندی را می\u200cخواهی به اشتراک بگذاری؟\n(تسک\u200cهای شخصی همان دسته هم وارد فضای مشترک می\u200cشوند)', parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def _after_category_chosen(update, context, team: dict, linked: int=0):
    query = update.callback_query
    extra = f'\n🔗 {linked} تسک به این دسته وصل شد.' if linked else ''
    await query.message.reply_text(f"📂 دسته\u200cبندی انتخاب\u200cشده: <b>{_e(team['name'])}</b>\n🆔 <code>{_e(team['team_id'])}</code>{extra}\n\nبا چه نقشی دعوت می\u200cکنی؟", parse_mode='HTML', reply_markup=_share_role_keyboard(team['team_id']))

async def _list_teams(update, context):
    user_id = update.effective_user.id
    items = await aget_user_teams(user_id)
    msg = update.callback_query.message if update.callback_query else update.message
    if not items:
        await msg.reply_text('هنوز عضو هیچ دسته\u200cبندی مشترکی نیستید.\nاز «📤 اشتراک\u200cگذاری دسته\u200cبندی» شروع کن یا لینک دعوت را باز کن.')
        return
    lines = [f'📂 دسته\u200cبندی\u200cهای مشترک شما ({len(items)}):\n']
    buttons = []
    for item in items:
        t = item['team']
        role = item['role']
        n = len(await aget_team_members(t['team_id']))
        lines.append(f"• <b>{_e(t['name'])}</b> — {role_label(role)} · 👤 {n}\n  🆔 <code>{_e(t['team_id'])}</code>")
        buttons.append([InlineKeyboardButton(f"📂 {t['name'][:22]}", callback_data=f"team_open_{t['team_id']}")])
    await msg.reply_text('\n'.join(lines), parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def team_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    user_id = user.id
    bot_user = await _bot_username(context)
    if data == 'team_menu':
        await _show_team_menu(update, context)
        return
    if data == 'team_share_start':
        await _start_share_wizard(update, context)
        return
    if data == 'team_share_new':
        context.user_data['step'] = 'team_share_new_name'
        await query.message.reply_text('نام دسته\u200cبندی\u200cای که می\u200cخواهی به اشتراک بگذاری را بنویس:')
        return
    if data.startswith('team_sharepick_t_'):
        team_id = data.replace('team_sharepick_t_', '', 1)
        team = get_team(team_id)
        if not team or not can_edit(team_id, user_id):
            await query.message.reply_text('دسترسی ندارید یا دسته پیدا نشد.')
            return
        linked = _sync_category_tasks(user_id, team)
        await _after_category_chosen(update, context, team, linked=linked)
        return
    if data.startswith('team_sharepick_c_'):
        cat = data.replace('team_sharepick_c_', '', 1)
        team = None
        for item in await aget_user_teams(user_id):
            t = item['team']
            if (t.get('name') or '').strip().lower() == cat.strip().lower() and item['role'] in (ROLE_OWNER, ROLE_EDITOR):
                team = t
                break
        if not team:
            team = create_team(user_id, cat, user=user)
            await query.message.reply_text(f'✅ فضای مشترک برای دسته «{cat}» ساخته شد.')
        linked = _sync_category_tasks(user_id, team)
        await _after_category_chosen(update, context, team, linked=linked)
        return
    if data == 'team_create':
        context.user_data['step'] = 'team_create_name'
        await query.message.reply_text('نام دسته\u200cبندی مشترک را وارد کنید:')
        return
    if data == 'team_join':
        context.user_data['step'] = 'team_join_code'
        await query.message.reply_text('کد دعوت یا لینک کامل را بفرست:')
        return
    if data == 'team_list':
        await _list_teams(update, context)
        return
    if data == 'team_help':
        await query.message.reply_text(_help_text(), parse_mode='HTML')
        return
    if data.startswith('team_open_'):
        await _open_team(update, context, data.replace('team_open_', '', 1))
        return
    if data.startswith('team_share_ed_'):
        await _send_share_invite(query, user_id, data.replace('team_share_ed_', '', 1), ROLE_EDITOR, bot_user)
        return
    if data.startswith('team_share_vw_'):
        await _send_share_invite(query, user_id, data.replace('team_share_vw_', '', 1), ROLE_VIEWER, bot_user)
        return
    if data.startswith('team_codes_'):
        team_id = data.replace('team_codes_', '', 1)
        team = get_team(team_id)
        if not team:
            await query.message.reply_text('پیدا نشد.')
            return
        if str(team.get('owner_id')) != str(user_id):
            await query.message.reply_text('فقط مالک.')
            return
        await query.message.reply_text(_codes_text(team, bot_user), parse_mode='HTML', reply_markup=_share_role_keyboard(team_id))
        return
    if data.startswith('team_regen_'):
        team_id = data.replace('team_regen_', '', 1)
        ok, msg, team = regenerate_codes(user_id, team_id)
        if ok and team:
            await query.message.reply_text(f'✅ {_e(msg)}\n\n' + _codes_text(team, bot_user), parse_mode='HTML')
        else:
            await query.message.reply_text('⚠️ ' + msg)
        return
    if data.startswith('team_leave_'):
        ok, msg = leave_team(user_id, data.replace('team_leave_', '', 1))
        await query.message.reply_text(('✅ ' if ok else '⚠️ ') + msg)
        return
    if data.startswith('team_members_'):
        team_id = data.replace('team_members_', '', 1)
        team = get_team(team_id)
        if not team or not any((i['team']['team_id'] == team_id for i in await aget_user_teams(user_id))):
            await query.message.reply_text('دسترسی ندارید.')
            return
        await query.message.reply_text(_format_members_list(team['name'], await aget_team_members(team_id)), parse_mode='HTML')
        return
    if data.startswith('team_tasks_'):
        await _show_team_tasks(update, context, data.replace('team_tasks_', '', 1))
        return
    if data.startswith('team_addtask_'):
        team_id = data.replace('team_addtask_', '', 1)
        if not can_edit(team_id, user_id):
            await query.message.reply_text('فقط ویرایشگر و مالک.')
            return
        context.user_data['new_task'] = {'team_id': team_id}
        context.user_data['step'] = 'title'
        team = get_team(team_id)
        await query.message.reply_text(f"📝 عنوان تسک برای دسته «{(team['name'] if team else team_id)}»:")
        return

async def _send_share_invite(query, user_id, team_id, role, bot_username):
    team = get_team(team_id)
    if not team:
        await query.message.reply_text('دسته پیدا نشد.')
        return
    if not can_edit(team_id, user_id):
        await query.message.reply_text('فقط مالک و ویرایشگر می\u200cتوانند دعوت بفرستند.')
        return
    _sync_category_tasks(user_id, team)
    bot_username = bot_username or BOT_USERNAME or 'TaskManagerpersian_Bot'
    text = _invite_message(team, role, bot_username)
    role_title = 'ویرایشگر' if role == ROLE_EDITOR else 'مشاهده\u200cکننده'
    await query.message.reply_text(f"📤 دعوت ({role_title})\n📂 دسته\u200cبندی در حال اشتراک: <b>{_e(team['name'])}</b>\n\nاین پیام را فوروارد کن:\n\n{text}", parse_mode='HTML')

async def _open_team(update, context, team_id: str):
    user_id = update.effective_user.id
    team = get_team(team_id)
    role = None
    for i in await aget_user_teams(user_id):
        if i['team']['team_id'] == team_id:
            role = i['role']
            break
    if not team or not role:
        await update.callback_query.message.reply_text('پیدا نشد یا عضو نیستید.')
        return
    linked = _sync_category_tasks(user_id, team)
    active = get_team_tasks(team_id, active_only=True)
    members = await aget_team_members(team_id)
    preview = '، '.join((_e(member_display(m)) for m in members[:5]))
    if len(members) > 5:
        preview += f' و {len(members) - 5} نفر دیگر'
    text = f"📂 دسته\u200cبندی مشترک: <b>{_e(team['name'])}</b>\n🆔 <code>{_e(team_id)}</code>\nنقش شما: {role_label(role)}\nتسک فعال: {len(active)}\nاعضا ({len(members)}): {preview}\n"
    if linked:
        text += f'🔗 {linked} تسک شخصی هم\u200cنام به این دسته وصل شد.\n'
    buttons = [[InlineKeyboardButton('📋 تسک\u200cهای این دسته', callback_data=f'team_tasks_{team_id}')], [InlineKeyboardButton(f'👥 اعضا ({len(members)})', callback_data=f'team_members_{team_id}')]]
    if can_edit(team_id, user_id):
        buttons.insert(0, [InlineKeyboardButton('➕ تسک در این دسته', callback_data=f'team_addtask_{team_id}')])
        buttons.append([InlineKeyboardButton('📤 اشتراک این دسته', callback_data=f'team_sharepick_t_{team_id}')])
    if role == ROLE_OWNER:
        buttons.append([InlineKeyboardButton('🔑 کدها و لینک\u200cها', callback_data=f'team_codes_{team_id}')])
        buttons.append([InlineKeyboardButton('🔄 تعویض کدها', callback_data=f'team_regen_{team_id}')])
    if role != ROLE_OWNER:
        buttons.append([InlineKeyboardButton('🚪 خروج', callback_data=f'team_leave_{team_id}')])
    buttons.append([InlineKeyboardButton('🔙 لیست', callback_data='team_list')])
    await update.callback_query.message.reply_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(buttons))

async def _show_team_tasks(update, context, team_id: str):
    user_id = update.effective_user.id
    team = get_team(team_id)
    if not team or not any((i['team']['team_id'] == team_id for i in await aget_user_teams(user_id))):
        await update.callback_query.message.reply_text('دسترسی ندارید.')
        return
    _sync_category_tasks(user_id, team)
    tasks = get_team_tasks(team_id, active_only=True)
    if not tasks:
        await update.callback_query.message.reply_text(f"دسته «{team['name']}» تسک فعالی ندارد.\nاگر تسک شخصی با همین نام دسته داری، یک\u200cبار «باز کردن این دسته» را بزن تا وصل شوند؛ یا با «➕ تسک در این دسته» تسک جدید بساز.")
        return
    pr = {'high': '🔴', 'medium': '🟠', 'low': '🟢'}
    st = {'pending': '⏳', 'in_progress': '🚀'}
    lines = [f"📋 تسک\u200cهای دسته «{_e(team['name'])}» — {len(tasks)}\n", f"📂 دسته\u200cبندی مشترک: <b>{_e(team['name'])}</b>\n"]
    for i, t in enumerate(tasks[:30], start=1):
        lines.append(f"{i}. {pr.get(t.get('priority'), '🟢')}{st.get(t.get('status'), '⏳')} {_e(t.get('title', '-'))} | {_e(t.get('deadline') or '—')} | <code>{_e(t.get('id'))}</code>")
    if not can_edit(team_id, user_id):
        lines.append('\n👁 فقط مشاهده.')
    await update.callback_query.message.reply_text('\n'.join(lines), parse_mode='HTML')

async def handle_team_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    step = context.user_data.get('step')
    if step not in ('team_create_name', 'team_join_code', 'team_share_new_name'):
        return False
    text = (update.message.text or '').strip()
    user = update.effective_user
    user_id = user.id
    bot_user = await _bot_username(context)
    if step == 'team_create_name':
        context.user_data.pop('step', None)
        if not text:
            await update.message.reply_text('نام خالی بود.')
            return True
        team = create_team(user_id, text, user=user)
        n = _sync_category_tasks(user_id, team)
        extra = f'\n🔗 {n} تسک شخصی وصل شد.' if n else ''
        await update.message.reply_text(f'✅ ساخته شد{extra}\n\n' + _codes_text(team, bot_user), parse_mode='HTML', reply_markup=_share_role_keyboard(team['team_id']))
        return True
    if step == 'team_share_new_name':
        context.user_data.pop('step', None)
        if not text:
            await update.message.reply_text('نام خالی بود.')
            return True
        team = create_team(user_id, text, user=user)
        n = _sync_category_tasks(user_id, team)
        extra = f'\n🔗 {n} تسک شخصی وصل شد.' if n else ''
        await update.message.reply_text(f"📂 دسته\u200cبندی «<b>{_e(team['name'])}</b>» آماده اشتراک است.{extra}\nنقش دعوت را انتخاب کن:", parse_mode='HTML', reply_markup=_share_role_keyboard(team['team_id']))
        return True
    if step == 'team_join_code':
        context.user_data.pop('step', None)
        await _do_join(update, context, _extract_code(text))
        return True
    return False
