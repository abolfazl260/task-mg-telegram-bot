from .tag_suggestions_legacy import *

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
