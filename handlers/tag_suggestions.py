from .tag_suggestions_legacy import *

_original_install_tag_flow = install_tag_flow


def install_tag_flow(task_module):
    """Install the existing smart-tag flow, then its create-task guards."""
    _original_install_tag_flow(task_module)
    from .create_task_flow import install_create_task_flow
    install_create_task_flow(task_module)
