from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"

text = MAIN.read_text(encoding="utf-8")

# Import runtime adapters and keep existing imports intact.
needle = "import handlers.task as task_handler\n"
insert = (
    needle
    + "\nfrom services import calendar_runtime\n"
    + "import handlers.reports as reports_handler\n"
    + "import handlers.extra_reports as extra_reports_handler\n"
)
if "import handlers.reports as reports_handler" not in text:
    text = text.replace(needle, insert, 1)

# Track the Telegram user for task-card rendering, including team-task viewers.
old = 'async def bind_bot_context(update, context):\n    profile = context.bot_data.get("bot_config")\n    set_current_bot_key(profile.key if profile else "default")\n'
new = 'async def bind_bot_context(update, context):\n    profile = context.bot_data.get("bot_config")\n    set_current_bot_key(profile.key if profile else "default")\n    calendar_runtime.set_current_user(update.effective_user.id if update.effective_user else None)\n'
if old in text and "calendar_runtime.set_current_user" not in text:
    text = text.replace(old, new, 1)

# Install adapters immediately after imports, before handlers are built.
marker = 'logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")\n'
patch = '''# Per-user calendar display adapters. Internal task dates remain Gregorian ISO.
task_handler.format_task_card = calendar_runtime.format_task_card
 task_handler.build_full_report = calendar_runtime.build_full_report
reports_handler.report_calendar = calendar_runtime.report_calendar
reports_handler.report_week = calendar_runtime.report_week
reports_handler.report_heatmap = calendar_runtime.report_heatmap
reports_handler.report_heatmap_week = calendar_runtime.report_heatmap_week
reports_handler.report_today = calendar_runtime.report_today
extra_reports_handler.report_compare_months = calendar_runtime.report_compare_months
report_compare_months = calendar_runtime.report_compare_months

'''.replace(" task_handler", "task_handler")
if "task_handler.format_task_card = calendar_runtime.format_task_card" not in text:
    text = text.replace(marker, marker + "\n" + patch, 1)

MAIN.write_text(text, encoding="utf-8")
print("calendar runtime adapters installed")
