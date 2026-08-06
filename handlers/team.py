"""Team / shared space commands and callbacks.

Share flow (category-based):
  1) User chooses which category/space to share
  2) User chooses role (editor / viewer)
  3) Bot sends ready-to-forward invite with correct deep link
"""

from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import BOT_USERNAME
from services.team_service import (
    create_team,
    join_team_by_code,
    find_team_by_code,
    get_user_teams,
    get_team,
    get_team_members,
    leave_team,
    regenerate_codes,
    role_label,
    member_display,
    ROLE_OWNER,
    ROLE_EDITOR,
    ROLE_VIEWER,
    can_edit,
)
from services.task_service import get_team_tasks, get_all_user_tasks


async def _bot_username(context) -> str:
    """Always prefer live username; fallback to config (TaskManagerpersian_Bot)."""

    try:
        if context.bot.username:
            return context.bot.username
        info = await context.bot.get_me()
        if info and info.username:
            return info.username
    except Exception:
        pass
    return BOT_USERNAME or "TaskManagerpersian_Bot"


def _deep_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start=join_{code}"


def _invite_message(team: dict, role: str, bot_username: str) -> str:
    code = team.get("editor_code") if role == ROLE_EDITOR else team.get("viewer_code")
    link = _deep_link(bot_username, code)
    role_fa = (
        "✏️ ویرایشگر — می‌تواند تسک بسازد و وضعیت را عوض کند"
        if role == ROLE_EDITOR
        else "👁 مشاهده‌کننده — فقط مشاهده تسک‌ها"
    )

    return (
        f"📨 دعوت به دسته‌بندی مشترک\n\n"
        f"📂 دسته‌بندی در حال اشتراک: **{team.get('name')}**\n"
        f"🆔 `{team.get('team_id')}`\n"
        f"نقش این دعوت: {role_fa}\n\n"
        f"عضویت با یک کلیک:\n{link}\n\n"
        f"یا در ربات بفرست:\n/team join {code}\n\n"
        f"—\nفقط همین دسته‌بندی («{team.get('name')}») به اشتراک گذاشته می‌شود."
    )


def _codes_text(team: dict, bot_username: str) -> str:
    ed = team.get("editor_code")
    vw = team.get("viewer_code")
    return (
        f"📂 دسته‌بندی: **{team.get('name')}**\n"
        f"🆔 `{team.get('team_id')}`\n\n"
        f"✏️ لینک ویرایشگر:\n{_deep_link(bot_username, ed)}\n"
        f"کد: `{ed}`\n\n"
        f"👁 لینک مشاهده:\n{_deep_link(bot_username, vw)}\n"
        f"کد: `{vw}`\n\n"
        f"⚠️ هر لینک نقش جدا دارد."
    )


def _format_members_list(team_name: str, members: list) -> str:
    owners = [m for m in members if m.get("role") == ROLE_OWNER]
    editors = [m for m in members if m.get("role") == ROLE_EDITOR]
    viewers = [m for m in members if m.get("role") == ROLE_VIEWER]

    lines = [
        f"👥 اعضای «{team_name}»\n",
        f"تعداد کل: **{len(members)}** نفر\n",
    ]

    def section(title, items):
        if not items:
            return
        lines.append(f"\n{title} ({len(items)}):")
        for i, m in enumerate(items, start=1):
            lines.append(f"  {i}. {member_display(m)}")
            lines.append(f"     🆔 `{m.get('user_id')}` · {m.get('joined_at') or '—'}")

    section("👑 مالک", owners)
    section("✏️ ویرایشگر", editors)
    section("👁 مشاهده‌کننده", viewers)
    return "\n".join(lines)


def _user_categories(user_id) -> list:
    """Unique non-empty categories from personal (non-team) tasks."""

    cats = []
    seen = set()
    for t in get_all_user_tasks(user_id):
        if (t.get("team_id") or "").strip():
            continue
        cat = (t.get("category") or "").strip()
        if not cat:
            continue
        key = cat.lower()
        if key not in seen:
            seen.add(key)
            cats.append(cat)
    return cats


async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    user = update.effective_user
    user_id = user.id
    bot_user = await _bot_username(context)

    if not args:
        await _show_team_menu(update, context)
        return

    action = args[0].lower()

    if action in ("create", "new", "ساخت"):
        name = " ".join(args[1:]).strip()
        if not name:
            context.user_data["step"] = "team_create_name"
            await update.message.reply_text("نام دسته‌بندی مشترک را وارد کنید:")
            return
        team = create_team(user_id, name, user=user)
        await update.message.reply_text(
            f"✅ دسته‌بندی مشترک ساخته شد\n\n" + _codes_text(team, bot_user),
            parse_mode="Markdown",
            reply_markup=_share_role_keyboard(team["team_id"]),
        )
        return

    if action in ("join", "عضویت"):
        if len(args) < 2:
            context.user_data["step"] = "team_join_code"
            await update.message.reply_text(
                "کد دعوت یا لینک را بفرست:\nمثال: `ABC12X`",
                parse_mode="Markdown",
            )
            return
        await _do_join(update, context, _extract_code(" ".join(args[1:])))
        return

    if action in ("share", "اشتراک", "اشتراک‌گذاری"):
        await _start_share_wizard(update, context)
        return

    if action in ("list", "لیست", "my"):
        await _list_teams(update, context)
        return

    if action in ("help", "راهنما"):
        await update.message.reply_text(_help_text(), parse_mode="Markdown")
        return

    await _show_team_menu(update, context)


def _extract_code(raw: str) -> str:
    s = (raw or "").strip()
    if "start=" in s:
        part = s.split("start=")[-1].split("&")[0].strip()
        for prefix in ("join_", "team_", "JOIN_", "TEAM_"):
            if part.startswith(prefix):
                part = part[len(prefix):]
                break
        return part.strip()
    return s.split()[0] if s else ""


async def _do_join(update, context, code: str):
    user = update.effective_user
    msg = update.message or (update.callback_query.message if update.callback_query else None)

    team_preview, role_preview = find_team_by_code(code)
    if not team_preview:
        if msg:
            await msg.reply_text("⚠️ کد دعوت نامعتبر است.")
        return

    role_fa = "✏️ ویرایشگر" if role_preview == ROLE_EDITOR else "👁 مشاهده‌کننده"
    ok, text, team = join_team_by_code(user.id, code, user=user)
    name = (team or team_preview).get("name")
    tid = (team or team_preview).get("team_id")

    if msg:
        await msg.reply_text(
            f"{'✅' if ok else '⚠️'} {text}\n\n"
            f"📂 دسته‌بندی: **{name}**\n"
            f"🆔 `{tid}`\n"
            f"نقش: {role_fa}",
            parse_mode="Markdown",
        )


def _help_text() -> str:
    return (
        "👥 **دسته‌بندی مشترک / تیم**\n\n"
        "**اشتراک‌گذاری (پیشنهادی):**\n"
        "۱) `/team share` یا دکمه 📤 اشتراک دسته‌بندی\n"
        "۲) انتخاب کن **کدام دسته‌بندی** را می‌خواهی به اشتراک بگذاری\n"
        "۳) نقش را انتخاب کن (ویرایشگر / مشاهده)\n"
        "۴) پیام دعوت را فوروارد کن\n\n"
        "**ساخت مستقیم:** `/team create نام`\n"
        "**عضویت:** لینک دعوت یا `/team join کد`\n"
    )


def _share_role_keyboard(team_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📤 دعوت ویرایشگر",
            callback_data=f"team_share_ed_{team_id}",
        )],
        [InlineKeyboardButton(
            "📤 دعوت مشاهده‌کننده",
            callback_data=f"team_share_vw_{team_id}",
        )],
        [InlineKeyboardButton(
            f"📂 باز کردن این دسته",
            callback_data=f"team_open_{team_id}",
        )],
    ])


async def _show_team_menu(update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 اشتراک‌گذاری دسته‌بندی", callback_data="team_share_start")],
        [InlineKeyboardButton("➕ ساخت دسته‌بندی مشترک", callback_data="team_create")],
        [InlineKeyboardButton("🔑 عضویت با کد / لینک", callback_data="team_join")],
        [InlineKeyboardButton("📋 دسته‌های مشترک من", callback_data="team_list")],
        [InlineKeyboardButton("❓ راهنما", callback_data="team_help")],
    ])
    text = (
        "👥 دسته‌بندی مشترک\n\n"
        "برای اشتراک، اول **انتخاب کن کدام دسته** را می‌خواهی به اشتراک بگذاری."
    )
    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(text, reply_markup=keyboard)


async def _start_share_wizard(update, context):
    """Step 1: ask which category/space to share."""

    user_id = update.effective_user.id
    msg = update.callback_query.message if update.callback_query else update.message

    buttons = []

    # Existing shared spaces user can invite to
    for item in get_user_teams(user_id):
        t = item["team"]
        role = item["role"]
        if role not in (ROLE_OWNER, ROLE_EDITOR):
            continue
        buttons.append([
            InlineKeyboardButton(
                f"📂 {t['name'][:28]} (مشترک)",
                callback_data=f"team_sharepick_t_{t['team_id']}",
            )
        ])

    # Personal task categories → can create/share as shared category
    for cat in _user_categories(user_id)[:15]:
        # avoid duplicate names already listed as teams
        buttons.append([
            InlineKeyboardButton(
                f"🏷 {cat[:28]} (از تسک‌های من)",
                callback_data=f"team_sharepick_c_{cat[:40]}",
            )
        ])

    buttons.append([
        InlineKeyboardButton("➕ نام جدید برای دسته مشترک", callback_data="team_share_new")
    ])
    buttons.append([
        InlineKeyboardButton("🔙 انصراف", callback_data="team_menu")
    ])

    if len(buttons) <= 2:
        # only new + cancel
        await msg.reply_text(
            "هنوز دسته‌بندی یا فضای مشترکی نداری.\n"
            "یک نام جدید بساز یا اول چند تسک با دسته ثبت کن.",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await msg.reply_text(
        "📤 **اشتراک‌گذاری بر اساس دسته‌بندی**\n\n"
        "کدام دسته‌بندی را می‌خواهی به اشتراک بگذاری؟\n"
        "(فقط همان دسته برای طرف مقابل مشترک می‌شود)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _after_category_chosen(update, context, team: dict):
    """Step 2: ask editor vs viewer for this category."""

    query = update.callback_query
    await query.message.reply_text(
        f"📂 دسته‌بندی انتخاب‌شده: **{team['name']}**\n"
        f"🆔 `{team['team_id']}`\n\n"
        f"با چه نقشی دعوت می‌کنی؟",
        parse_mode="Markdown",
        reply_markup=_share_role_keyboard(team["team_id"]),
    )


async def _list_teams(update, context):
    user_id = update.effective_user.id
    items = get_user_teams(user_id)
    msg = update.callback_query.message if update.callback_query else update.message

    if not items:
        await msg.reply_text(
            "هنوز عضو هیچ دسته‌بندی مشترکی نیستید.\n"
            "از «📤 اشتراک‌گذاری دسته‌بندی» شروع کن یا لینک دعوت را باز کن."
        )
        return

    lines = [f"📂 دسته‌بندی‌های مشترک شما ({len(items)}):\n"]
    buttons = []
    for item in items:
        t = item["team"]
        role = item["role"]
        n = len(get_team_members(t["team_id"]))
        lines.append(
            f"• **{t['name']}** — {role_label(role)} · 👤 {n}\n"
            f"  🆔 `{t['team_id']}`"
        )
        buttons.append([
            InlineKeyboardButton(
                f"📂 {t['name'][:22]}",
                callback_data=f"team_open_{t['team_id']}",
            )
        ])

    await msg.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def team_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    user_id = user.id
    bot_user = await _bot_username(context)

    if data == "team_menu":
        await _show_team_menu(update, context)
        return

    if data == "team_share_start":
        await _start_share_wizard(update, context)
        return

    if data == "team_share_new":
        context.user_data["step"] = "team_share_new_name"
        await query.message.reply_text(
            "نام دسته‌بندی‌ای که می‌خواهی به اشتراک بگذاری را بنویس:"
        )
        return

    if data.startswith("team_sharepick_t_"):
        team_id = data.replace("team_sharepick_t_", "", 1)
        team = get_team(team_id)
        if not team or not can_edit(team_id, user_id):
            await query.message.reply_text("دسترسی ندارید یا دسته پیدا نشد.")
            return
        await _after_category_chosen(update, context, team)
        return

    if data.startswith("team_sharepick_c_"):
        cat = data.replace("team_sharepick_c_", "", 1)
        # find existing team with same name owned/editable, else create
        team = None
        for item in get_user_teams(user_id):
            t = item["team"]
            if t.get("name") == cat and item["role"] in (ROLE_OWNER, ROLE_EDITOR):
                team = t
                break
        if not team:
            team = create_team(user_id, cat, user=user)
            await query.message.reply_text(
                f"✅ فضای مشترک برای دسته «{cat}» ساخته شد."
            )
        await _after_category_chosen(update, context, team)
        return

    if data == "team_create":
        context.user_data["step"] = "team_create_name"
        await query.message.reply_text("نام دسته‌بندی مشترک را وارد کنید:")
        return

    if data == "team_join":
        context.user_data["step"] = "team_join_code"
        await query.message.reply_text(
            "کد دعوت یا لینک کامل را بفرست:",
        )
        return

    if data == "team_list":
        await _list_teams(update, context)
        return

    if data == "team_help":
        await query.message.reply_text(_help_text(), parse_mode="Markdown")
        return

    if data.startswith("team_open_"):
        await _open_team(update, context, data.replace("team_open_", "", 1))
        return

    if data.startswith("team_share_ed_"):
        await _send_share_invite(
            query, user_id, data.replace("team_share_ed_", "", 1), ROLE_EDITOR, bot_user
        )
        return

    if data.startswith("team_share_vw_"):
        await _send_share_invite(
            query, user_id, data.replace("team_share_vw_", "", 1), ROLE_VIEWER, bot_user
        )
        return

    if data.startswith("team_codes_"):
        team_id = data.replace("team_codes_", "", 1)
        team = get_team(team_id)
        if not team:
            await query.message.reply_text("پیدا نشد.")
            return
        if str(team.get("owner_id")) != str(user_id):
            await query.message.reply_text("فقط مالک.")
            return
        await query.message.reply_text(
            _codes_text(team, bot_user),
            parse_mode="Markdown",
            reply_markup=_share_role_keyboard(team_id),
        )
        return

    if data.startswith("team_regen_"):
        team_id = data.replace("team_regen_", "", 1)
        ok, msg, team = regenerate_codes(user_id, team_id)
        if ok and team:
            await query.message.reply_text(
                f"✅ {msg}\n\n" + _codes_text(team, bot_user),
                parse_mode="Markdown",
            )
        else:
            await query.message.reply_text("⚠️ " + msg)
        return

    if data.startswith("team_leave_"):
        ok, msg = leave_team(user_id, data.replace("team_leave_", "", 1))
        await query.message.reply_text(("✅ " if ok else "⚠️ ") + msg)
        return

    if data.startswith("team_members_"):
        team_id = data.replace("team_members_", "", 1)
        team = get_team(team_id)
        if not team or not any(
            i["team"]["team_id"] == team_id for i in get_user_teams(user_id)
        ):
            await query.message.reply_text("دسترسی ندارید.")
            return
        await query.message.reply_text(
            _format_members_list(team["name"], get_team_members(team_id)),
            parse_mode="Markdown",
        )
        return

    if data.startswith("team_tasks_"):
        await _show_team_tasks(update, context, data.replace("team_tasks_", "", 1))
        return

    if data.startswith("team_addtask_"):
        team_id = data.replace("team_addtask_", "", 1)
        if not can_edit(team_id, user_id):
            await query.message.reply_text("فقط ویرایشگر و مالک.")
            return
        context.user_data["new_task"] = {"team_id": team_id}
        context.user_data["step"] = "title"
        team = get_team(team_id)
        await query.message.reply_text(
            f"📝 عنوان تسک برای دسته «{team['name'] if team else team_id}»:"
        )
        return


async def _send_share_invite(query, user_id, team_id, role, bot_username):
    team = get_team(team_id)
    if not team:
        await query.message.reply_text("دسته پیدا نشد.")
        return
    if not can_edit(team_id, user_id):
        await query.message.reply_text("فقط مالک و ویرایشگر می‌توانند دعوت بفرستند.")
        return

    # force correct bot username in link
    bot_username = bot_username or BOT_USERNAME or "TaskManagerpersian_Bot"
    text = _invite_message(team, role, bot_username)
    role_title = "ویرایشگر" if role == ROLE_EDITOR else "مشاهده‌کننده"
    await query.message.reply_text(
        f"📤 دعوت ({role_title})\n"
        f"📂 دسته‌بندی در حال اشتراک: **{team['name']}**\n\n"
        f"این پیام را فوروارد کن:\n\n{text}",
        parse_mode="Markdown",
    )


async def _open_team(update, context, team_id: str):
    user_id = update.effective_user.id
    team = get_team(team_id)
    role = None
    for i in get_user_teams(user_id):
        if i["team"]["team_id"] == team_id:
            role = i["role"]
            break

    if not team or not role:
        await update.callback_query.message.reply_text("پیدا نشد یا عضو نیستید.")
        return

    active = get_team_tasks(team_id, active_only=True)
    members = get_team_members(team_id)
    preview = "، ".join(member_display(m) for m in members[:5])
    if len(members) > 5:
        preview += f" و {len(members) - 5} نفر دیگر"

    text = (
        f"📂 دسته‌بندی مشترک: **{team['name']}**\n"
        f"🆔 `{team_id}`\n"
        f"نقش شما: {role_label(role)}\n"
        f"تسک فعال: {len(active)}\n"
        f"اعضا ({len(members)}): {preview}\n"
    )

    buttons = [
        [InlineKeyboardButton("📋 تسک‌های این دسته", callback_data=f"team_tasks_{team_id}")],
        [InlineKeyboardButton(f"👥 اعضا ({len(members)})", callback_data=f"team_members_{team_id}")],
    ]
    if can_edit(team_id, user_id):
        buttons.insert(0, [
            InlineKeyboardButton("➕ تسک در این دسته", callback_data=f"team_addtask_{team_id}")
        ])
        buttons.append([
            InlineKeyboardButton("📤 اشتراک این دسته", callback_data=f"team_sharepick_t_{team_id}"),
        ])
    if role == ROLE_OWNER:
        buttons.append([InlineKeyboardButton("🔑 کدها و لینک‌ها", callback_data=f"team_codes_{team_id}")])
        buttons.append([InlineKeyboardButton("🔄 تعویض کدها", callback_data=f"team_regen_{team_id}")])
    if role != ROLE_OWNER:
        buttons.append([InlineKeyboardButton("🚪 خروج", callback_data=f"team_leave_{team_id}")])
    buttons.append([InlineKeyboardButton("🔙 لیست", callback_data="team_list")])

    await update.callback_query.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def _show_team_tasks(update, context, team_id: str):
    user_id = update.effective_user.id
    team = get_team(team_id)
    if not team or not any(i["team"]["team_id"] == team_id for i in get_user_teams(user_id)):
        await update.callback_query.message.reply_text("دسترسی ندارید.")
        return

    tasks = get_team_tasks(team_id, active_only=True)
    if not tasks:
        await update.callback_query.message.reply_text(
            f"دسته «{team['name']}» تسک فعالی ندارد."
        )
        return

    pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}
    st = {"pending": "⏳", "in_progress": "🚀"}
    lines = [
        f"📋 تسک‌های دسته «{team['name']}» — {len(tasks)}\n",
        f"📂 دسته‌بندی مشترک: **{team['name']}**\n",
    ]
    for i, t in enumerate(tasks[:30], start=1):
        lines.append(
            f"{i}. {pr.get(t.get('priority'), '🟢')}{st.get(t.get('status'), '⏳')} "
            f"{t.get('title', '-')} | {t.get('deadline') or '—'} | `{t.get('id')}`"
        )
    if not can_edit(team_id, user_id):
        lines.append("\n👁 فقط مشاهده.")

    await update.callback_query.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )


async def handle_team_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    step = context.user_data.get("step")
    if step not in ("team_create_name", "team_join_code", "team_share_new_name"):
        return False

    text = (update.message.text or "").strip()
    user = update.effective_user
    user_id = user.id
    bot_user = await _bot_username(context)

    if step == "team_create_name":
        context.user_data.pop("step", None)
        if not text:
            await update.message.reply_text("نام خالی بود.")
            return True
        team = create_team(user_id, text, user=user)
        await update.message.reply_text(
            f"✅ ساخته شد\n\n" + _codes_text(team, bot_user),
            parse_mode="Markdown",
            reply_markup=_share_role_keyboard(team["team_id"]),
        )
        return True

    if step == "team_share_new_name":
        context.user_data.pop("step", None)
        if not text:
            await update.message.reply_text("نام خالی بود.")
            return True
        team = create_team(user_id, text, user=user)
        await update.message.reply_text(
            f"📂 دسته‌بندی «**{team['name']}**» آماده اشتراک است.\n"
            f"نقش دعوت را انتخاب کن:",
            parse_mode="Markdown",
            reply_markup=_share_role_keyboard(team["team_id"]),
        )
        return True

    if step == "team_join_code":
        context.user_data.pop("step", None)
        await _do_join(update, context, _extract_code(text))
        return True

    return False
