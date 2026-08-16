"""Per-bot task capability enforcement."""
from __future__ import annotations
from functools import wraps
from typing import Any, Awaitable, Callable
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DEFAULT_TASK_OPTIONS={"allow_assignment":True,"allow_tags":True,"allow_comments":True,"allow_categories":True,"allow_priority":True,"allow_search":True,"allow_templates":True,"allow_bulk_import":True,"allow_ai_task_creation":True}
_WRAPPABLE_CALLBACKS={"assignment_callback","assignment_manage_callback","take_assignment","take_confirm","safe_assignment_confirm","comment_callback","comment_cancel_callback","button_handler","priority_selected","deadline_selected","optional_field_callback","save_task"}

def task_options(profile):
    result=DEFAULT_TASK_OPTIONS.copy();raw=(getattr(profile,"settings",{}) or {}).get("task_options",{}) or {};result.update({k:bool(v) for k,v in raw.items() if k in result});return result

def task_option_enabled(context,name):
    profile=context.bot_data.get("bot_config") if context is not None else None;return task_options(profile).get(name,True)

async def _show_no_assignment_confirmation(update,context):
    task=context.user_data.get("new_task") or {};task["assignee"]=None;task["team_id"]=""
    if not task_option_enabled(context,"allow_tags"):task["tags"]=""
    if not task_option_enabled(context,"allow_categories"):task["category"]=""
    if not task_option_enabled(context,"allow_priority"):task["priority"]="medium"
    context.user_data["new_task"]=task;context.user_data["step"]="task_confirm_create"
    keyboard=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید و ثبت",callback_data="task_confirm_create")],[InlineKeyboardButton("❌ لغو",callback_data="task_cancel_create")]])
    handler=__import__("handlers.task",fromlist=["_assignment_summary"]);summary=handler._assignment_summary(task).replace("👤 مسئول:\n❌ تعیین نشده\n\n","");await update.effective_message.reply_text(summary,reply_markup=keyboard)

async def _finalize_without_assignment(update,context):
    handler=__import__("handlers.task",fromlist=["_finalize_task"]);task=context.user_data.get("new_task") or {};task["assignee"]=None;task["team_id"]=""
    if not task_option_enabled(context,"allow_tags"):task["tags"]=""
    if not task_option_enabled(context,"allow_categories"):task["category"]=""
    if not task_option_enabled(context,"allow_priority"):task["priority"]="medium"
    task_id=await handler._finalize_task(update.effective_user.id,task);context.user_data.clear();await update.effective_message.reply_text(f"✅ تسک ثبت شد\n🆔 {task_id}")

def wrap_save_task(original):
    @wraps(original)
    async def wrapper(update,context):
        step=context.user_data.get("step");task=context.user_data.get("new_task")
        if not task:return await original(update,context)
        if step=="title" and not task_option_enabled(context,"allow_priority"):
            task["priority"]="medium";context.user_data["step"]="deadline"
            from utils.keyboard import deadline_keyboard
            await update.effective_message.reply_text("📅 زمان انجام را انتخاب کنید یا بدون زمان‌بندی ثبت کنید:",reply_markup=deadline_keyboard());return
        if step=="category" and not task_option_enabled(context,"allow_categories"):
            task["category"]="";task["tags"]="";context.user_data["step"]="description"
            handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.effective_message,context);return
        if step=="tags" and not task_option_enabled(context,"allow_tags"):
            task["tags"]="";handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.effective_message,context);return
        if step=="description" and not task_option_enabled(context,"allow_assignment"):
            task["description"]=update.effective_message.text or "";await _show_no_assignment_confirmation(update,context);return
        return await original(update,context)
    return wrapper

def wrap_priority_selected(original):
    @wraps(original)
    async def wrapper(update,context):
        if not task_option_enabled(context,"allow_priority"):
            query=update.callback_query;await query.answer();context.user_data.setdefault("new_task",{})["priority"]="medium";context.user_data["step"]="deadline"
            from utils.keyboard import deadline_keyboard
            await query.message.edit_text("📅 زمان انجام را انتخاب کنید یا بدون زمان‌بندی ثبت کنید:",reply_markup=deadline_keyboard());return
        return await original(update,context)
    return wrapper

def wrap_deadline_selected(original):
    @wraps(original)
    async def wrapper(update,context):
        if not task_option_enabled(context,"allow_categories"):
            query=update.callback_query;await query.answer();data=query.data.replace("deadline_","");task=context.user_data.setdefault("new_task",{})
            if data=="custom":context.user_data["step"]="deadline_custom";await query.message.reply_text("📅 تاریخ دقیق را وارد کنید:");return
            if data=="none":task["deadline"]=""
            else:
                from datetime import datetime,timedelta
                task["deadline"]=(datetime.now()+timedelta(days=int(data))).strftime("%Y-%m-%d")
            context.user_data["step"]="description";handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(query.message,context);return
        return await original(update,context)
    return wrapper

def wrap_optional_field_callback(original):
    @wraps(original)
    async def wrapper(update,context):
        data=update.callback_query.data or "";task=context.user_data.get("new_task") or {}
        if data.startswith("category_") and not task_option_enabled(context,"allow_categories"):
            task["category"]="";task["tags"]="";context.user_data["new_task"]=task;handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.callback_query.message,context);await update.callback_query.answer();return
        if data.startswith("tags_") and not task_option_enabled(context,"allow_tags"):
            task["tags"]="";context.user_data["new_task"]=task;handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.callback_query.message,context);await update.callback_query.answer();return
        return await original(update,context)
    return wrapper

def wrap_callback(original):
    @wraps(original)
    async def wrapper(update,context):
        data=(update.callback_query.data or "") if update.callback_query else ""
        if data.startswith("ai_task_"):
            if not task_option_enabled(context,"allow_ai_task_creation"):await update.callback_query.answer("ایجاد تسک با هوش مصنوعی برای این ربات فعال نیست.",show_alert=True);return
            draft=context.user_data.get("ai_request_draft")
            if isinstance(draft,dict):_sanitize_ai_draft(context,draft)
        if data in {"task_confirm_create","task_cancel_create"} and not task_option_enabled(context,"allow_assignment"):
            await update.callback_query.answer()
            if data=="task_confirm_create":await _finalize_without_assignment(update,context)
            else:context.user_data.clear();await update.callback_query.message.reply_text("❌ ایجاد تسک لغو شد.")
            return
        if data.startswith(("assign_","owner_","take_","asg_","chg_")) and not task_option_enabled(context,"allow_assignment"):await update.callback_query.answer("تخصیص مسئول برای این ربات فعال نیست.",show_alert=True);return
        if data.startswith("comment_") and not task_option_enabled(context,"allow_comments"):await update.callback_query.answer("کامنت برای این ربات فعال نیست.",show_alert=True);return
        if data.startswith(("tag_","tags_","step_back_tags")) and not task_option_enabled(context,"allow_tags"):await update.callback_query.answer("تگ برای این ربات فعال نیست.",show_alert=True);return
        return await original(update,context)
    return wrapper

def _sanitize_ai_draft(context,draft):
    if not task_option_enabled(context,"allow_tags"):draft["tags"]=""
    if not task_option_enabled(context,"allow_categories"):draft["category"]=""
    if not task_option_enabled(context,"allow_assignment"):draft["assignee"]=None;draft["team_id"]=""
    if not task_option_enabled(context,"allow_priority"):draft["priority"]="medium"
    return draft

def install_task_capabilities(app):
    state=getattr(app,"bot_data",None)
    if state is None:return
    if state.get("_task_capabilities_installed",False):return
    for handlers in app.handlers.values():
        for handler in handlers:
            callback=getattr(handler,"callback",None);name=getattr(callback,"__name__","")
            if name not in _WRAPPABLE_CALLBACKS or getattr(callback,"_task_capability_wrapped",False):continue
            if name=="save_task":wrapped=wrap_save_task(callback)
            elif name=="priority_selected":wrapped=wrap_priority_selected(callback)
            elif name=="deadline_selected":wrapped=wrap_deadline_selected(callback)
            elif name=="optional_field_callback":wrapped=wrap_optional_field_callback(callback)
            else:wrapped=wrap_callback(callback)
            setattr(wrapped,"_task_capability_wrapped",True);handler.callback=wrapped
    state["_task_capabilities_installed"]=True
