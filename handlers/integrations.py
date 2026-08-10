from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.async_bridge import integration as integration_service

PROVIDERS = {
    "microsoft": "🪟 Microsoft To Do",
    "google": "🔵 Google Tasks",
}


def _bot_key(context):
    profile = context.bot_data.get("bot_config")
    return profile.key if profile else "default"


async def integrations_keyboard(user_id, bot_key="default"):
    rows = []
    for provider, label in PROVIDERS.items():
        if await integration_service.connected(user_id, provider, bot_key):
            rows.append([InlineKeyboardButton(f"{label} ✅", callback_data=f"int_menu_{provider}")])
        else:
            rows.append([InlineKeyboardButton(label, callback_data=f"int_connect_{provider}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="settings")])
    return InlineKeyboardMarkup(rows)


async def provider_keyboard(user_id, provider, bot_key="default"):
    connection = await integration_service.get_connection(user_id, provider, bot_key)
    list_name = connection.get("external_list_name") if connection else ""
    rows = [
        [InlineKeyboardButton("🔄 همگام‌سازی الآن", callback_data=f"int_sync_{provider}")],
        [InlineKeyboardButton("📋 انتخاب فهرست", callback_data=f"int_lists_{provider}")],
    ]
    if list_name:
        rows.insert(0, [InlineKeyboardButton(f"📌 فهرست فعلی: {list_name}", callback_data=f"int_lists_{provider}")])
    rows.append([InlineKeyboardButton("🔌 قطع اتصال", callback_data=f"int_disconnect_{provider}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="integrations")])
    return InlineKeyboardMarkup(rows)


def lists_keyboard(provider, lists):
    rows = []
    for item in lists[:20]:
        list_id = item.get("id", "")
        name = item.get("displayName") or item.get("title") or "بدون نام"
        rows.append([InlineKeyboardButton(f"📋 {name}", callback_data=f"int_setlist_{provider}_{list_id}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"int_menu_{provider}")])
    return InlineKeyboardMarkup(rows)


def _bot_key(context):
    profile = context.bot_data.get("bot_config")
    return profile.key if profile else "default"


async def show_integrations(update, context):
    user_id = update.effective_user.id
    await update.callback_query.message.reply_text(
        "🔗 اتصال سرویس‌ها\n\nمی‌توانید حساب خود را به یکی از سرویس‌های مدیریت کار متصل کنید.\n\nبا اتصال، تسک‌های ربات با سرویس انتخاب‌شده همگام می‌شوند.",
        reply_markup=await integrations_keyboard(user_id, _bot_key(context)),
    )


async def integration_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    bot_key = _bot_key(context)

    if data == "integrations":
        await show_integrations(update, context)
        return

    if data.startswith("int_connect_"):
        provider = data.replace("int_connect_", "", 1)
        try:
            url = await integration_service.start_oauth(provider, user_id, bot_key)
            await query.message.reply_text(
                f"🔐 برای اتصال {PROVIDERS.get(provider, provider)} روی دکمه زیر بزنید و اجازه دسترسی به تسک‌ها را تأیید کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 اتصال حساب", url=url)], [InlineKeyboardButton("🔙 بازگشت", callback_data="integrations")]]),
            )
        except Exception as exc:
            await query.message.reply_text(f"⚠️ امکان شروع اتصال وجود ندارد:\n{exc}")
        return

    if data.startswith("int_menu_"):
        provider = data.replace("int_menu_", "", 1)
        await query.message.reply_text(
            f"{PROVIDERS.get(provider, provider)}\n\nاتصال فعال است.\nمی‌توانید فهرست مقصد را انتخاب کنید یا همگام‌سازی را اجرا کنید.",
            reply_markup=await provider_keyboard(user_id, provider, bot_key),
        )
        return

    if data.startswith("int_lists_"):
        provider = data.replace("int_lists_", "", 1)
        try:
            lists = await integration_service.get_lists(user_id, provider, bot_key)
            if not lists:
                await query.message.reply_text("⚠️ هیچ فهرستی پیدا نشد.")
                return
            await query.message.reply_text("📋 فهرست مقصد را انتخاب کنید:", reply_markup=lists_keyboard(provider, lists))
        except Exception as exc:
            await query.message.reply_text(f"⚠️ دریافت فهرست‌ها ناموفق بود:\n{exc}")
        return

    if data.startswith("int_setlist_"):
        parts = data.split("_", 3)
        if len(parts) < 4:
            return
        provider, list_id = parts[2], parts[3]
        try:
            lists = await integration_service.get_lists(user_id, provider, bot_key)
            chosen = next((x for x in lists if x.get("id") == list_id), None)
            if not chosen:
                await query.message.reply_text("⚠️ فهرست انتخاب‌شده پیدا نشد.")
                return
            name = chosen.get("displayName") or chosen.get("title") or "بدون نام"
            await integration_service.set_list(user_id, provider, list_id, name, bot_key)
            await query.message.reply_text("✅ فهرست مقصد تنظیم شد.", reply_markup=await provider_keyboard(user_id, provider, bot_key))
        except Exception as exc:
            await query.message.reply_text(f"⚠️ ذخیره فهرست ناموفق بود:\n{exc}")
        return

    if data.startswith("int_sync_"):
        provider = data.replace("int_sync_", "", 1)
        try:
            results = await integration_service.sync_user(user_id, bot_key, provider)
            result = results[0] if results else (provider, 0, None)
            if result[2]:
                await query.message.reply_text(f"⚠️ همگام‌سازی انجام نشد:\n{result[2]}")
            else:
                await query.message.reply_text(f"✅ همگام‌سازی انجام شد.\nتعداد تغییرات: {result[1]}", reply_markup=await provider_keyboard(user_id, provider, bot_key))
        except Exception as exc:
            await query.message.reply_text(f"⚠️ خطا در همگام‌سازی:\n{exc}")
        return

    if data.startswith("int_disconnect_"):
        provider = data.replace("int_disconnect_", "", 1)
        await integration_service.disconnect(user_id, provider, bot_key)
        await query.message.reply_text("🔌 اتصال قطع شد.", reply_markup=await integrations_keyboard(user_id, bot_key))
