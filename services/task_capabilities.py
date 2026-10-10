"""Per-bot task capability enforcement."""
from __future__ import annotations
from functools import wraps
from typing import Any, Awaitable, Callable
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DEFAULT_TASK_OPTIONS={"allow_assignment":True,"allow_tags":True,"allow_comments":True,"allow_categories":True,"allow_priority":True,"allow_search":True,"allow_templates":True,"allow_bulk_import":True,"allow_ai_task_creation":True}
_WRAPPABLE_CALLBACKS={"assignment_callback","assignment_manage_callback","take_assignment","take_confirm","safe_assignment_confirm","comment_callback","comment_cancel_callback","button_handler","priority_selected","deadline_selected","optional_field_callback","save_task","save_task_with_progress","priority_rich","deadline_rich","optional_with_media_description","assignment_with_rich_final_state"}

def task_options(profile):
    result=DEFAULT_TASK_OPTIONS.copy();raw=(getattr(profile,"settings",{}) or {}).get("task_options",{}) or {};result.update({k:bool(v) for k,v in raw.items() if k in result});return result

def task_option_enabled(context,name):
    bot_data=getattr(context,"bot_data",{}) if context is not None else {}
    profile=(bot_data or {}).get("bot_config");return task_options(profile).get(name,True)

def task_permission_enabled(context,name):
    bot_data=getattr(context,"bot_data",{}) if context is not None else {}
    profile=(bot_data or {}).get("bot_config")
    checker=getattr(profile,"permission_enabled",None)
    return profile is None or checker is None or bool(checker(name))

def task_creation_allowed(context):
    bot_data = getattr(context, "bot_data", {}) or {}
    profile = bot_data.get("bot_config")
    feature_enabled = getattr(profile, "feature_enabled", None)
    return (profile is None or feature_enabled is None or bool(feature_enabled("tasks"))) and task_permission_enabled(context, "tasks.create")


_CREATE_FIELD_RULES = {
    "priority": ("priority", "priority.set", "allow_priority"),
    "deadline": ("deadline", "deadline.set", None),
    "category": ("categories", "categories.manage", "allow_categories"),
    "tags": ("tags", "tags.manage", "allow_tags"),
    "assignment": ("assignment", "assignment.manage", "allow_assignment"),
}


def task_creation_field_enabled(context, field):
    """Single capability contract for create-task UI and its callbacks."""
    feature, permission, option = _CREATE_FIELD_RULES[field]
    profile = (getattr(context, "bot_data", {}) or {}).get("bot_config")
    checker = getattr(profile, "feature_enabled", None)
    return (
        task_creation_allowed(context)
        and (profile is None or checker is None or bool(checker(feature)))
        and task_permission_enabled(context, permission)
        and (option is None or task_option_enabled(context, option))
    )


async def _deny_create_operation(update):
    query = getattr(update, "callback_query", None)
    if query is not None:
        await query.answer("ایجاد تسک برای این ربات مجاز نیست.", show_alert=True)
    elif getattr(update, "effective_message", None) is not None:
        await update.effective_message.reply_text("⛔️ ایجاد تسک برای این ربات مجاز نیست.")


def wrap_rich_create_handler(original):
    """Do not rely on legacy handler names for the dynamically installed Rich flow."""
    @wraps(original)
    async def wrapper(update, context):
        if not task_creation_allowed(context):
            await _deny_create_operation(update)
            return
        return await original(update, context)
    return wrapper


async def _show_no_assignment_confirmation(update,context):
    task=context.user_data.get("new_task") or {};task["assignee"]=None;task["team_id"]=""
    if not task_option_enabled(context,"allow_tags") or not task_permission_enabled(context,"tags.manage"):task["tags"]=""
    if not task_option_enabled(context,"allow_categories") or not task_permission_enabled(context,"categories.manage"):task["category"]=""
    if not task_option_enabled(context,"allow_priority") or not task_permission_enabled(context,"priority.set"):task["priority"]="medium"
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
        if not task_permission_enabled(context,"tasks.create"):
            await update.effective_message.reply_text("⛔️ ایجاد تسک برای این ربات مجاز نیست.")
            return
        message=update.effective_message
        has_attachment=bool(
            message and (
                getattr(message,"photo",None)
                or getattr(message,"video",None)
                or getattr(message,"document",None)
            )
        )
        if has_attachment and not task_permission_enabled(context,"attachments.manage"):
            await message.reply_text("⛔️ افزودن پیوست برای این ربات مجاز نیست.")
            return
        step=context.user_data.get("step");task=context.user_data.get("new_task")
        if not task:return await original(update,context)
        if step=="title" and (not task_option_enabled(context,"allow_priority") or not task_permission_enabled(context,"priority.set")):
            task["priority"]="medium";context.user_data["step"]="deadline"
            from utils.keyboard import deadline_keyboard
            await update.effective_message.reply_text("📅 زمان انجام را انتخاب کنید یا بدون زمان‌بندی ثبت کنید:",reply_markup=deadline_keyboard());return
        if step=="category" and (not task_option_enabled(context,"allow_categories") or not task_permission_enabled(context,"categories.manage")):
            task["category"]="";task["tags"]="";context.user_data["step"]="description"
            handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.effective_message,context);return
        if step=="tags" and (not task_option_enabled(context,"allow_tags") or not task_permission_enabled(context,"tags.manage")):
            task["tags"]="";handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.effective_message,context);return
        if step=="description" and (not task_option_enabled(context,"allow_assignment") or not task_permission_enabled(context,"assignment.manage")):
            task["description"]=update.effective_message.text or "";await _show_no_assignment_confirmation(update,context);return
        return await original(update,context)
    return wrapper

def wrap_priority_selected(original):
    @wraps(original)
    async def wrapper(update,context):
        if not task_option_enabled(context,"allow_priority") or not task_permission_enabled(context,"priority.set"):
            query=update.callback_query;await query.answer();context.user_data.setdefault("new_task",{})["priority"]="medium";context.user_data["step"]="deadline"
            from utils.keyboard import deadline_keyboard
            await query.message.edit_text("📅 زمان انجام را انتخاب کنید یا بدون زمان‌بندی ثبت کنید:",reply_markup=deadline_keyboard());return
        return await original(update,context)
    return wrapper

def wrap_deadline_selected(original):
    @wraps(original)
    async def wrapper(update,context):
        if not task_permission_enabled(context,"deadline.set"):
            await update.callback_query.answer("تنظیم ددلاین برای این ربات مجاز نیست.",show_alert=True);return
        if not task_option_enabled(context,"allow_categories") or not task_permission_enabled(context,"categories.manage"):
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
        if data.startswith("category_") and (not task_option_enabled(context,"allow_categories") or not task_permission_enabled(context,"categories.manage")):
            task["category"]="";task["tags"]="";context.user_data["new_task"]=task;handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.callback_query.message,context);await update.callback_query.answer();return
        if data.startswith("tags_") and (not task_option_enabled(context,"allow_tags") or not task_permission_enabled(context,"tags.manage")):
            task["tags"]="";context.user_data["new_task"]=task;handler=__import__("handlers.task",fromlist=["_ask_description"]);await handler._ask_description(update.callback_query.message,context);await update.callback_query.answer();return
        return await original(update,context)
    return wrapper

def wrap_callback(original):
    @wraps(original)
    async def wrapper(update,context):
        data=(update.callback_query.data or "") if update.callback_query else ""
        if data.startswith("ai_task_"):
            if not task_option_enabled(context,"allow_ai_task_creation") or not task_permission_enabled(context,"ai.tasks.create") or not task_permission_enabled(context,"tasks.create"):await update.callback_query.answer("ایجاد تسک با هوش مصنوعی برای این ربات مجاز نیست.",show_alert=True);return
            draft=context.user_data.get("ai_request_draft")
            if isinstance(draft,dict):_sanitize_ai_draft(context,draft)
        if data in {"task_confirm_create","task_cancel_create"} and not task_permission_enabled(context,"tasks.create"):
            await update.callback_query.answer("ایجاد تسک برای این ربات مجاز نیست.",show_alert=True);return
        if data in {"task_confirm_create","task_cancel_create"} and (not task_option_enabled(context,"allow_assignment") or not task_permission_enabled(context,"assignment.manage")):
            await update.callback_query.answer()
            if data=="task_confirm_create":await _finalize_without_assignment(update,context)
            else:context.user_data.clear();await update.callback_query.message.reply_text("❌ ایجاد تسک لغو شد.")
            return
        if data.startswith(("assign_","owner_","take_","asg_","chg_")) and (not task_option_enabled(context,"allow_assignment") or not task_permission_enabled(context,"assignment.manage")):await update.callback_query.answer("تخصیص مسئول برای این ربات مجاز نیست.",show_alert=True);return
        if data.startswith("comment_") and (not task_option_enabled(context,"allow_comments") or not task_permission_enabled(context,"comments.manage")):await update.callback_query.answer("کامنت برای این ربات مجاز نیست.",show_alert=True);return
        if data.startswith(("tag_","tags_","step_back_tags")) and (not task_option_enabled(context,"allow_tags") or not task_permission_enabled(context,"tags.manage")):await update.callback_query.answer("تگ برای این ربات مجاز نیست.",show_alert=True);return
        if data in {"template_open", "import_bulk"}:
            option = "allow_templates" if data == "template_open" else "allow_bulk_import"
            permission = "templates.use" if data == "template_open" else "bulk_import.use"
            if not task_option_enabled(context, option) or not task_permission_enabled(context, permission):
                await update.callback_query.answer("این قابلیت برای این ربات فعال نیست.", show_alert=True)
                return
        return await original(update,context)
    return wrapper

def _sanitize_ai_draft(context,draft):
    if not task_option_enabled(context,"allow_tags") or not task_permission_enabled(context,"tags.manage"):draft["tags"]=""
    if not task_option_enabled(context,"allow_categories") or not task_permission_enabled(context,"categories.manage"):draft["category"]=""
    if not task_option_enabled(context,"allow_assignment") or not task_permission_enabled(context,"assignment.manage"):draft["assignee"]=None;draft["team_id"]=""
    if not task_option_enabled(context,"allow_priority") or not task_permission_enabled(context,"priority.set"):draft["priority"]="medium"
    return draft

def install_task_capabilities(app):
    if app is None:return
    state=getattr(app,"bot_data",None)
    if state is None:state={}
    if state.get("_task_capabilities_installed",False) or getattr(app,"_task_capabilities_installed",False):return
    for handlers in app.handlers.values():
        for handler in handlers:
            callback=getattr(handler,"callback",None);name=getattr(callback,"__name__","")
            if name not in _WRAPPABLE_CALLBACKS or getattr(callback,"_task_capability_wrapped",False):continue
            if name in {"save_task_with_progress","priority_rich","deadline_rich","optional_with_media_description","assignment_with_rich_final_state"}:wrapped=wrap_rich_create_handler(callback)
            elif name=="save_task":wrapped=wrap_save_task(callback)
            elif name=="priority_selected":wrapped=wrap_priority_selected(callback)
            elif name=="deadline_selected":wrapped=wrap_deadline_selected(callback)
            elif name=="optional_field_callback":wrapped=wrap_optional_field_callback(callback)
            else:wrapped=wrap_callback(callback)
            setattr(wrapped,"_task_capability_wrapped",True);handler.callback=wrapped
    state["_task_capabilities_installed"]=True
    try:
        setattr(app,"_task_capabilities_installed",True)
    except (AttributeError,TypeError):
        # telegram.ext.Application uses slots; bot_data remains the canonical state.
        pass
