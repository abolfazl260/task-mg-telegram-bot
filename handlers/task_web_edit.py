from urllib.parse import quote

from webapp.config import WEBAPP_BASE_URL
from webapp.report_tokens import create_report_token
from services.task_service import get_task_by_id_async, user_can_modify_task_async
from bot_context import get_current_bot_key


async def task_web_edit_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    task_id = data.replace("task_web_edit_", "", 1)
    task = await get_task_by_id_async(task_id)
    if not task or not await user_can_modify_task_async(update.effective_user.id, task):
        await query.answer("تسک پیدا نشد یا دسترسی ویرایش ندارید.", show_alert=True)
        return

    bot_key = get_current_bot_key() or "default"
    token = create_report_token(bot_key, str(update.effective_user.id), report_type="task", ttl_days=30)
    url = f"{WEBAPP_BASE_URL.rstrip('/')}/task/{quote(token, safe='')}/{quote(str(task_id), safe='')}"
    await query.answer(url=url)
