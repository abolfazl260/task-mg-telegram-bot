"""Team / shared space commands and callbacks."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.team_service import (
    create_team,
    join_team_by_code,
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
from services.task_service import get_team_tasks


def _codes_text(team: dict) -> str:
    return (
        f"✏️ کد ویرایشگر (ادیتور):\n`{team.get('editor_code')}`\n"
        f"/team join {team.get('editor_code')}\n\n"
        f"👁 کد مشاهده‌کننده:\n`{team.get('viewer_code')}`\n"
        f"/team join {team.get('viewer_code')}\n\n"
        f"⚠️ لینک‌ها/کدها متفاوت‌اند — نقش با کد تعیین می‌شود."
    )


def _format_members_list(team_name: str, members: list) -> str:
    """Readable roster of team members."""

    owners = [m for m in members if m.get("role") == ROLE_OWNER]
    editors = [m for m in members if m.get("role") == ROLE_EDITOR]
    viewers = [m for m in members if m.get("role") == ROLE_VIEWER]

    lines = [
        f"👥 اعضای تیم «{team_name}»\n",
        f"تعداد کل: **{len(members)}** نفر\n",
    ]

    def section(title, items):
        if not items:
            return
        lines.append(f"\n{title} ({len(items)}):")
        for i, m in enumerate(items, start=1):
            label = member_display(m)
            joined = m.get("joined_at") or "—"
            lines.append(f"  {i}. {label}")
            lines.append(f"     🆔 `{m.get('user_id')}` · عضویت: {joined}")

    section("👑 مالک", owners)
    section("✏️ ویرایشگر", editors)
    section("👁 مشاهده‌کننده", viewers)

    return "\n".join(lines)


async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /team
    /team create نام تیم
    /team join CODE
    /team list
    """

    args = context.args or []
    user = update.effective_user
    user_id = user.id

    if not args:
        await _show_team_menu(update, context)
        return

    action = args[0].lower()

    if action in ("create", "new", "ساخت"):
        name = " ".join(args[1:]).strip()
        if not name:
            context.user_data["step"] = "team_create_name"
            await update.message.reply_text("نام تیم را وارد کنید:")
            return
        team = create_team(user_id, name, user=user)
        text = (
            f"✅ تیم «**{team['name']}**» ساخته شد.\n"
            f"🆔 `{team['team_id']}`\n\n"
            + _codes_text(team)
        )
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    if action in ("join", "عضویت"):
        if len(args) < 2:
            context.user_data["step"] = "team_join_code"
            await update.message.reply_text(
                "کد دعوت را وارد کنید:\n(یا: /team join ABC12X)"
            )
            return
        code = args[1].strip()
        ok, msg, team = join_team_by_code(user_id, code, user=user)
        await update.message.reply_text(
            ("✅ " if ok else "⚠️ ") + msg
            + (f"\n🆔 `{team['team_id']}`" if team and ok else ""),
            parse_mode="Markdown",
        )
        return

    if action in ("list", "لیست", "my"):
        await _list_teams(update, context)
        return

    if action in ("help", "راهنما"):
        await update.message.reply_text(_help_text(), parse_mode="Markdown")
        return

    await _show_team_menu(update, context)


def _help_text() -> str:
    return (
        "👥 **تیم / فضای مشترک**\n\n"
        "• `/team create نام` — ساخت تیم (شما مالک می‌شوید)\n"
        "• `/team join کد` — عضویت با کد دعوت\n"
        "• `/team list` — تیم‌های من\n\n"
        "**نقش‌ها:**\n"
        "👑 مالک — مدیریت + کدهای دعوت\n"
        "✏️ ویرایشگر — ساخت و تغییر تسک تیمی\n"
        "👁 مشاهده‌کننده — فقط مشاهده\n\n"
        "هر تیم دو کد جدا دارد (ادیتور / مشاهده).\n"
        "می‌توانید عضو چند تیم همزمان باشید.\n"
        "از داخل هر تیم دکمه **👥 اعضا** لیست افراد را نشان می‌دهد."
    )


async def _show_team_menu(update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ساخت تیم", callback_data="team_create")],
        [InlineKeyboardButton("🔑 عضویت با کد", callback_data="team_join")],
        [InlineKeyboardButton("📋 تیم‌های من", callback_data="team_list")],
        [InlineKeyboardButton("❓ راهنما", callback_data="team_help")],
    ])
    text = "👥 بخش تیم‌ها\n\nچه کاری می‌خواهید؟"
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)


async def _list_teams(update, context):
    user_id = update.effective_user.id
    items = get_user_teams(user_id)
    msg = update.callback_query.message if update.callback_query else update.message

    if not items:
        await msg.reply_text(
            "هنوز عضو هیچ تیمی نیستید.\n"
            "با /team create یک تیم بسازید یا /team join کد دعوت."
        )
        return

    lines = [f"👥 تیم‌های شما ({len(items)}):\n"]
    buttons = []
    for item in items:
        t = item["team"]
        role = item["role"]
        members = get_team_members(t["team_id"])
        lines.append(
            f"• **{t['name']}** — {role_label(role)}\n"
            f"  🆔 `{t['team_id']}` · 👤 {len(members)} عضو"
        )
        buttons.append([
            InlineKeyboardButton(
                f"📂 {t['name'][:20]} ({len(members)})",
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

    if data == "team_menu":
        await _show_team_menu(update, context)
        return

    if data == "team_create":
        context.user_data["step"] = "team_create_name"
        await query.message.reply_text("نام تیم را وارد کنید:")
        return

    if data == "team_join":
        context.user_data["step"] = "team_join_code"
        await query.message.reply_text("کد دعوت را وارد کنید:")
        return

    if data == "team_list":
        await _list_teams(update, context)
        return

    if data == "team_help":
        await query.message.reply_text(_help_text(), parse_mode="Markdown")
        return

    if data.startswith("team_open_"):
        team_id = data.replace("team_open_", "", 1)
        await _open_team(update, context, team_id)
        return

    if data.startswith("team_codes_"):
        team_id = data.replace("team_codes_", "", 1)
        team = get_team(team_id)
        if not team:
            await query.message.reply_text("تیم پیدا نشد.")
            return
        if str(team.get("owner_id")) != str(user_id):
            await query.message.reply_text("فقط مالک کدهای دعوت را می‌بیند.")
            return
        await query.message.reply_text(
            f"🔑 کدهای دعوت — **{team['name']}**\n\n" + _codes_text(team),
            parse_mode="Markdown",
        )
        return

    if data.startswith("team_regen_"):
        team_id = data.replace("team_regen_", "", 1)
        ok, msg, team = regenerate_codes(user_id, team_id)
        if ok and team:
            await query.message.reply_text(
                f"✅ {msg}\n\n" + _codes_text(team),
                parse_mode="Markdown",
            )
        else:
            await query.message.reply_text("⚠️ " + msg)
        return

    if data.startswith("team_leave_"):
        team_id = data.replace("team_leave_", "", 1)
        ok, msg = leave_team(user_id, team_id)
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
        members = get_team_members(team_id)
        text = _format_members_list(team["name"], members)
        await query.message.reply_text(text, parse_mode="Markdown")
        return

    if data.startswith("team_tasks_"):
        team_id = data.replace("team_tasks_", "", 1)
        await _show_team_tasks(update, context, team_id)
        return

    if data.startswith("team_addtask_"):
        team_id = data.replace("team_addtask_", "", 1)
        if not can_edit(team_id, user_id):
            await query.message.reply_text("فقط ویرایشگر و مالک می‌توانند تسک تیمی بسازند.")
            return
        context.user_data["new_task"] = {"team_id": team_id}
        context.user_data["step"] = "title"
        team = get_team(team_id)
        name = team["name"] if team else team_id
        await query.message.reply_text(
            f"📝 عنوان تسک تیمی برای «{name}» را وارد کنید:"
        )
        return


async def _open_team(update, context, team_id: str):
    user_id = update.effective_user.id
    team = get_team(team_id)
    items = get_user_teams(user_id)
    role = None
    for i in items:
        if i["team"]["team_id"] == team_id:
            role = i["role"]
            break

    if not team or not role:
        await update.callback_query.message.reply_text("تیم پیدا نشد یا عضو نیستید.")
        return

    active = get_team_tasks(team_id, active_only=True)
    members = get_team_members(team_id)

    # short preview of members
    preview_names = []
    for m in members[:5]:
        preview_names.append(member_display(m))
    extra = len(members) - 5
    preview = "، ".join(preview_names)
    if extra > 0:
        preview += f" و {extra} نفر دیگر"

    text = (
        f"📂 **{team['name']}**\n"
        f"🆔 `{team_id}`\n"
        f"نقش شما: {role_label(role)}\n"
        f"تسک فعال: {len(active)}\n"
        f"اعضا ({len(members)}): {preview}\n"
    )

    buttons = [
        [InlineKeyboardButton("📋 تسک‌های تیم", callback_data=f"team_tasks_{team_id}")],
        [InlineKeyboardButton(
            f"👥 اعضا ({len(members)})",
            callback_data=f"team_members_{team_id}",
        )],
    ]
    if can_edit(team_id, user_id):
        buttons.insert(0, [
            InlineKeyboardButton("➕ تسک تیمی", callback_data=f"team_addtask_{team_id}")
        ])
    if role == ROLE_OWNER:
        buttons.append([
            InlineKeyboardButton("🔑 کدهای دعوت", callback_data=f"team_codes_{team_id}")
        ])
        buttons.append([
            InlineKeyboardButton("🔄 تعویض کدها", callback_data=f"team_regen_{team_id}")
        ])
    if role != ROLE_OWNER:
        buttons.append([
            InlineKeyboardButton("🚪 خروج از تیم", callback_data=f"team_leave_{team_id}")
        ])
    buttons.append([InlineKeyboardButton("🔙 تیم‌های من", callback_data="team_list")])

    await update.callback_query.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
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
            f"تیم «{team['name']}» تسک فعالی ندارد."
        )
        return

    pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}
    st = {"pending": "⏳", "in_progress": "🚀"}
    lines = [f"📋 تسک‌های «{team['name']}» — {len(tasks)}:\n"]
    for i, t in enumerate(tasks[:30], start=1):
        lines.append(
            f"{i}. {pr.get(t.get('priority'), '🟢')}{st.get(t.get('status'), '⏳')} "
            f"{t.get('title', '-')} | {t.get('deadline') or '—'} | `{t.get('id')}`"
        )
    if len(tasks) > 30:
        lines.append(f"... و {len(tasks) - 30} مورد دیگر")

    if not can_edit(team_id, user_id):
        lines.append("\n👁 شما مشاهده‌کننده هستید — فقط مشاهده.")

    await update.callback_query.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )


async def handle_team_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle pending team create/join text steps. Return True if consumed."""

    step = context.user_data.get("step")
    if step not in ("team_create_name", "team_join_code"):
        return False

    text = (update.message.text or "").strip()
    user = update.effective_user
    user_id = user.id

    if step == "team_create_name":
        context.user_data.pop("step", None)
        if not text:
            await update.message.reply_text("نام خالی بود.")
            return True
        team = create_team(user_id, text, user=user)
        await update.message.reply_text(
            f"✅ تیم «**{team['name']}**» ساخته شد.\n🆔 `{team['team_id']}`\n\n"
            + _codes_text(team),
            parse_mode="Markdown",
        )
        return True

    if step == "team_join_code":
        context.user_data.pop("step", None)
        ok, msg, team = join_team_by_code(user_id, text, user=user)
        await update.message.reply_text(
            ("✅ " if ok else "⚠️ ") + msg,
            parse_mode="Markdown",
        )
        return True

    return False
