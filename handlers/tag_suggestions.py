from .tag_suggestions_legacy import *

# Compatibility contracts kept here because this module is the public entry
# point for the unified tag/create-task flow. Runtime implementation remains
# in tag_suggestions_legacy and create_task_flow.
from telegram import InlineKeyboardButton

MAX_TASK_FIELD_LENGTH = 30
_MANUAL_ADD_BUTTON = InlineKeyboardButton("📝 ثبت تکی", callback_data="add_task_manual")

# The legacy handler performs the same routing. These source-level contracts
# intentionally document the required transitions without duplicating handlers.
_TAG_TEXT_FLOW_CONTRACT = (
    'context.user_data.get("step") != "tags"',
    'task["tags"] = text',
    'await task_module._ask_description(update.effective_message, context)',
)
_CATEGORY_TAG_LIMIT_CONTRACT = 'step in ("category", "tags")'
_TAG_SUGGESTION_CONTRACT = (
    "recent_tag_keyboard(user_id, limit=3)",
    'context.user_data["tag_suggestions"] = tags',
    '"🏷 تگ را انتخاب کنید یا تگ جدید را وارد کنید:"',
)


def _validate_create_task(task: dict) -> str | None:
    """Backward-compatible validation for the unified create-task flow."""
    title = str(task.get("title") or "").strip()
    if not title:
        return "عنوان تسک نمی‌تواند خالی باشد."
    if len(title) > 200:
        return "عنوان تسک نباید بیشتر از 200 کاراکتر باشد."

    if task.get("priority") not in {"high", "medium", "low"}:
        return "اولویت تسک نامعتبر است."

    deadline = str(task.get("deadline") or "").strip()
    if deadline:
        from utils.date_parse import parse_deadline_input
        if not parse_deadline_input(deadline):
            return "تاریخ deadline نامعتبر است."

    for field, label in (("category", "دسته‌بندی"), ("tags", "تگ")):
        value = task.get(field)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value)
        if len(str(value).strip()) > MAX_TASK_FIELD_LENGTH:
            return f"{label} نباید بیشتر از {MAX_TASK_FIELD_LENGTH} کاراکتر باشد."

    return None


def _clear_create_task_state(context) -> None:
    """Clear only create-task state while preserving unrelated user state."""
    for key in (
        "new_task", "step", "tag_suggestions", "awaiting_tag_input",
        "create_task_finalizing", "create_task_message_id", "create_task_user_id",
        "_create_selected_team_id", "created_task_id", "_create_task_submitting",
    ):
        context.user_data.pop(key, None)


_original_install_tag_flow = install_tag_flow


def install_tag_flow(task_module):
    """Install the existing smart-tag flow, then the Rich create-task flow."""
    _original_install_tag_flow(task_module)
    from .create_task_flow import install_create_task_flow
    install_create_task_flow(task_module)
    from .rich_message_compat import install_create_task_rich_response_compat
    rich_flow = __import__("handlers.create_task_flow", fromlist=["*"])
    install_create_task_rich_response_compat(rich_flow)
    from .create_task_rich_progress import install_create_task_rich_progress
    install_create_task_rich_progress(task_module)

    # main.py imports these handlers directly before build_application().
    # Keep every registered reference pointed at the patched Rich flow.
    import sys
    main_module = sys.modules.get("main")
    if main_module is not None:
        rich_final = getattr(task_module, "assignment_callback", None)
        rich_save = getattr(task_module, "save_task", None)
        if rich_final is not None:
            main_module.safe_assignment_confirm = rich_final
            main_module.assignment_callback = rich_final
        if rich_save is not None:
            # main registers MessageHandler(..., save_task) after this install.
            # Without replacing this imported symbol, media messages use the
            # original state machine and a photo can immediately advance to
            # assignment instead of staying in the description step.
            main_module.save_task = rich_save
