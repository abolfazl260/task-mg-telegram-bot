"""Safe category callbacks for manual task creation."""
from hashlib import sha1
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from services.task_service import get_active_tasks_async


def category_key(category: str) -> str:
    return sha1(category.strip().encode("utf-8")).hexdigest()[:12]

async def category_keyboard(user_id) -> InlineKeyboardMarkup:
    categories = []
    seen = set()
    for task in await get_active_tasks_async(user_id):
        category = (task.get("category") or "").strip()
        key = category.lower()
        if category and key not in seen:
            seen.add(key)
            categories.append(category)
    rows = [
        [InlineKeyboardButton(f"📂 {category}", callback_data=f"category_pick_{category_key(category)}")]
        for category in categories[:10]
    ]
    rows.append([InlineKeyboardButton("⏭ رد کردن", callback_data="category_skip")])
    return InlineKeyboardMarkup(rows)

async def handle_category_callback(update, context) -> bool:
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("category_pick_"):
        return False
    await query.answer()
    task = context.user_data.get("new_task")
    if task is None:
        await query.message.reply_text("فرایند ایجاد تسک فعالی پیدا نشد.")
        return True
    wanted = data[len("category_pick_"):]
    for existing in await get_active_tasks_async(update.effective_user.id):
        category = (existing.get("category") or "").strip()
        if category and category_key(category) == wanted:
            task["category"] = category
            context.user_data["step"] = "tags"
            await query.message.reply_text("🏷 تگ را وارد کنید یا دکمه «رد کردن» را بزنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ رد کردن", callback_data="tags_skip")]]))
            return True
    await query.message.reply_text("⚠️ این دسته‌بندی دیگر در دسترس نیست. لطفاً دوباره انتخاب کنید.")
    return True
