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

    # main.py imports safe_assignment_confirm directly before build_application().
    # Replace that imported reference as well, otherwise the legacy guard can
    # bypass the Rich finalization wrapper.
    import sys
    main_module = sys.modules.get("main")
    if main_module is not None:
        rich_final = getattr(task_module, "assignment_callback", None)
        if rich_final is not None:
            main_module.safe_assignment_confirm = rich_final
            main_module.assignment_callback = rich_final
