"""Team / shared space commands and callbacks."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

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
from services.task_service import get_team_tasks


async def _bot_username(context) -> str:
    me = context.bot.username
    if me:
        return me
    try:
        info = await context.bot.get_me()
        return info.username or "YourBot"
    except Exception:
        return "YourBot"


def _deep_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start=join_{code}"


def _invite_message(team: dict, role: str, bot_username: str) -> str:
    """Ready-to-forward invite. Clearly states team name + role."""

    code = team.get("editor_code") if role == ROLE_EDITOR else team.get("viewer_code")
    link = _deep_link(bot_username, code)
    role_fa = (
        "✏️ ویرایشگر — می‌تواند تسک بسازد و وضعیت را عوض کند"
        if role == ROLE_EDITOR
        else "👁 مشاهده‌کننده — فقط مشاهده تسک‌ها"
    )

    return (
        f"📨 دعوت به فضای مشترک\n\n"
        f"📂 تیم / دسته‌بندی: **{team.get('name')}**\n"
        f"🆔 `{team.get('team_id')}`\n"
        f"نقش این دعوت: {role_fa}\n\n"
        f"برای عضویت یک‌ضرب روی لینک بزن:\n{link}\n\n"
        f"یا در ربات بفرست:\n`/team join {code}`\n\n"
        f"—\nاین دعوت مخصوص تیم «{team.get('name')}» است."
    )


def _codes_text(team: dict, bot_username: str = "YourBot") -> str:
    ed = team.get("editor_code")
    vw = team.get("viewer_code")
    return (
        f"📂 تیم: **{team.get('name')}**\n"
        f"🆔 `{team.get('team_id')}`\n\n"
        f"✏️ دعوت ویرایشگر:\n"
        f"{_deep_link(bot_username, ed)}\n"
        f"یا `/team join {ed}`\n\n"
        f"👁 دعوت مشاهده‌کننده:\n"
        f"{_deep_link(bot_username, vw)}\n"
        f"یا `/team join {vw}`\n\n"
        f"⚠️ هر لینک نقش جدا دارد — قبل از فوروارد نقش را چک کن."
    )


def _format_members_list(team_name: str, members: list) -> str:
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
            await update.message.reply_text("نام تیم / دسته‌بندی مشترک را وارد کنید:")
            return
        team = create_team(user_id, name, user=user)
        text = (
            f"✅ فضای مشترک ساخته شد\n\n"
            f"📂 نام: **{team['name']}**\n"
            f"🆔 `{team['team_id']}`\n\n"
            + _codes_text(team, bot_user)
            + "\n\n💡 از دکمه‌های زیر پیام آمادهٔ فوروارد بگیر."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📤 اشتراک لینک ویرایشگر",
                callback_data=f"team_share_ed_{team['team_id']}",
            )],
            [InlineKeyboardButton(
                "📤 اشتراک لینک مشاهده",
                callback_data=f"team_share_vw_{team['team_id']}",
            )],
            [InlineKeyboardButton(
                f"📂 باز کردن «{team['name'][:18]}»",
                callback_data=f"team_open_{team['team_id']}",
            )],
        ])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if action in ("join", "عضویت"):
        if len(args) < 2:
            context.user_data["step"] = "team_join_code"
            await update.message.reply_text(
                "کد دعوت یا لینک را وارد کنید:\n"
                "مثال: `ABC12X` یا کل لینک t.me/..."
                ,
                parse_mode="Markdown",
            )
            return
        code = _extract_code(" ".join(args[1:]))
        await _do_join(update, context, code)
        return

    if action in ("list", "لیست", "my"):
        await _list_teams(update, context)
        return

    if action in ("help", "راهنما"):
        await update.message.reply_text(_help_text(), parse_mode="Markdown")
        return

    await _show_team_menu(update, context)


def _extract_code(raw: str) -> str:
    """Accept plain code or full t.me deep link."""

    s = (raw or "").strip()
    if "start=" in s:
        # https://t.me/bot?start=join_ABC12X
        part = s.split("start=")[-1].split("&")[0].strip()
        for prefix in ("join_", "team_", "JOIN_", "TEAM_"):
            if part.startswith(prefix):
                part = part[len(prefix):]
                break
        return part.strip()
    # /team join CODE
    return s.split()[0] if s else ""


async def _do_join(update, context, code: str):
    user = update.effective_user
    msg = update.message or (update.callback_query.message if update.callback_query else None)

    team_preview, role_preview = find_team_by_code(code)
    if not team_preview:
        if msg:
            await msg.reply_text("⚠️ کد دعوت نامعتبر است.")
        return

    role_fa = (
        "✏️ ویرایشگر"
        if role_preview == ROLE_EDITOR
        else "👁 مشاهده‌کننده"
    )
    ok, text, team = join_team_by_code(user.id, code, user=user)
    name = (team or team_preview).get("name")
    tid = (team or team_preview).get("team_id")

    body = (
        f"{'✅' if ok else '⚠️'} {text}\n\n"
        f"📂 تیم / دسته‌بندی: **{name}**\n"
        f"🆔 `{tid}`\n"
        f"نقش این دعوت: {role_fa}"
    )
    if msg:
        await msg.reply_text(body, parse_mode="Markdown")


def _help_text() -> str:
    return (
        "👥 **تیم / فضای مشترک**\n\n"
        "**ساخت:**\n`/team create نام‌دسته`\n\n"
        "**عضویت (ساده‌ترین راه):**\n"
        "روی لینک دعوت بزن — خودکار عضو می‌شوی.\n"
        "یا: `/team join کد`\n\n"
        "**اشتراک‌گذاری:**\n"
        "داخل تیم → 📤 اشتراک لینک ویرایشگر / مشاهده\n"
        "پیام آماده را فوروارد کن؛ نام تیم روی پیام مشخص است.\n\n"
        "👑 مالک · ✏️ ویرایشگر · 👁 مشاهده‌کننده"
    )


async def _show_team_menu(update, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ساخت تیم", callback_data="team_create")],
        [InlineKeyboardButton("🔑 عضویت با کد / لینک", callback_data="team_join")],
        [InlineKeyboardButton("📋 تیم‌های من", callback_data="team_list")],
        [InlineKeyboardButton("❓ راهنما", callback_data="team_help")],
    ])
    text = (
        "👥 بخش تیم‌ها\n\n"
        "هر تیم یک **دسته‌بندی / فضای مشترک** است.\n"
        "چه کاری می‌خواهید؟"
    )
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
            "با /team create بساز یا لینک دعوت را باز کن."
        )
        return

    lines = [f"👥 فضاهای مشترک شما ({len(items)}):\n"]
    buttons = []
    for item in items:
        t = item["team"]
        role = item["role"]
        members = get_team_members(t["team_id"])
        lines.append(
            f"• 📂 **{t['name']}** — {role_label(role)}\n"
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
    bot_user = await _bot_username(context)

    if data == "team_menu":
        await _show_team_menu(update, context)
        return

    if data == "team_create":
        context.user_data["step"] = "team_create_name"
        await query.message.reply_text("نام تیم / دسته‌بندی مشترک را وارد کنید:")
        return

    if data == "team_join":
        context.user_data["step"] = "team_join_code"
        await query.message.reply_text(
            "کد دعوت یا لینک کامل را بفرست:\n"
            "مثال: `ABC12X` یا لینک t.me/...",
            parse_mode="Markdown",
        )
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

    if data.startswith("team_share_ed_"):
        team_id = data.replace("team_share_ed_", "", 1)
        await _send_share_invite(query, user_id, team_id, ROLE_EDITOR, bot_user)
        return

    if data.startswith("team_share_vw_"):
        team_id = data.replace("team_share_vw_", "", 1)
        await _send_share_invite(query, user_id, team_id, ROLE_VIEWER, bot_user)
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
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📤 اشتراک لینک ویرایشگر",
                callback_data=f"team_share_ed_{team_id}",
            )],
            [InlineKeyboardButton(
                "📤 اشتراک لینک مشاهده",
                callback_data=f"team_share_vw_{team_id}",
            )],
        ])
        await query.message.reply_text(
            _codes_text(team, bot_user),
            parse_mode="Markdown",
            reply_markup=kb,
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
            f"📝 عنوان تسک برای فضای «{name}» را وارد کنید:"
        )
        return


async def _send_share_invite(query, user_id, team_id, role, bot_username):
    team = get_team(team_id)
    if not team:
        await query.message.reply_text("تیم پیدا نشد.")
        return
    # owner or editor can share invites
    items = get_user_teams(user_id)
    my_role = None
    for i in items:
        if i["team"]["team_id"] == team_id:
            my_role = i["role"]
            break
    if my_role not in (ROLE_OWNER, ROLE_EDITOR):
        await query.message.reply_text("فقط مالک و ویرایشگر می‌توانند دعوت بفرستند.")
        return

    text = _invite_message(team, role, bot_username)
    role_title = "ویرایشگر" if role == ROLE_EDITOR else "مشاهده‌کننده"
    await query.message.reply_text(
        f"📤 پیام دعوت ({role_title}) برای تیم **{team['name']}**\n"
        f"این پیام را فوروارد کن:\n\n" + text,
        parse_mode="Markdown",
    )


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

    preview_names = [member_display(m) for m in members[:5]]
    extra = len(members) - 5
    preview = "، ".join(preview_names)
    if extra > 0:
        preview += f" و {extra} نفر دیگر"

    text = (
        f"📂 فضای مشترک: **{team['name']}**\n"
        f"🆔 `{team_id}`\n"
        f"نقش شما: {role_label(role)}\n"
        f"تسک فعال: {len(active)}\n"
        f"اعضا ({len(members)}): {preview}\n"
    )

    buttons = [
        [InlineKeyboardButton("📋 تسک‌های این فضا", callback_data=f"team_tasks_{team_id}")],
        [InlineKeyboardButton(
            f"👥 اعضا ({len(members)})",
            callback_data=f"team_members_{team_id}",
        )],
    ]
    if can_edit(team_id, user_id):
        buttons.insert(0, [
            InlineKeyboardButton("➕ تسک در این فضا", callback_data=f"team_addtask_{team_id}")
        ])
        buttons.append([
            InlineKeyboardButton("📤 دعوت ویرایشگر", callback_data=f"team_share_ed_{team_id}"),
            InlineKeyboardButton("📤 دعوت مشاهده", callback_data=f"team_share_vw_{team_id}"),
        ])
    if role == ROLE_OWNER:
        buttons.append([
            InlineKeyboardButton("🔑 همه کدها / لینک‌ها", callback_data=f"team_codes_{team_id}")
        ])
        buttons.append([
            InlineKeyboardButton("🔄 تعویض کدها", callback_data=f"team_regen_{team_id}")
        ])
    if role != ROLE_OWNER:
        buttons.append([
            InlineKeyboardButton("🚪 خروج از این فضا", callback_data=f"team_leave_{team_id}")
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
            f"فضای «{team['name']}» تسک فعالی ندارد."
        )
        return

    pr = {"high": "🔴", "medium": "🟠", "low": "🟢"}
    st = {"pending": "⏳", "in_progress": "🚀"}
    lines = [
        f"📋 تسک‌های فضای «{team['name']}» — {len(tasks)}:\n",
        f"📂 دسته‌بندی مشترک: **{team['name']}**\n",
    ]
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
    step = context.user_data.get("step")
    if step not in ("team_create_name", "team_join_code"):
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
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📤 اشتراک لینک ویرایشگر",
                callback_data=f"team_share_ed_{team['team_id']}",
            )],
            [InlineKeyboardButton(
                "📤 اشتراک لینک مشاهده",
                callback_data=f"team_share_vw_{team['team_id']}",
            )],
        ])
        await update.message.reply_text(
            f"✅ فضای مشترک ساخته شد\n\n"
            f"📂 نام: **{team['name']}**\n"
            f"🆔 `{team['team_id']}`\n\n"
            + _codes_text(team, bot_user),
            parse_mode="Markdown",
            reply_markup=kb,
        )
        return True

    if step == "team_join_code":
        context.user_data.pop("step", None)
        code = _extract_code(text)
        await _do_join(update, context, code)
        return True

    return False
