from datetime import datetime, timedelta
import logging
import jdatetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from services.task_service import create_task_async, get_active_tasks_async, get_task_by_id_async, change_task_status_async, user_can_modify_task_async, assign_task_async, get_unassigned_tasks_async, add_task_comment_async, get_task_comments_async
from services.csv_export import build_csv_bytes
from services.team_service import aget_user_teams, aget_team_members, member_display
from utils.keyboard import priority_keyboard, deadline_keyboard, task_action_keyboard
from utils.date_parse import parse_deadline_input
from handlers.search_share import handle_search_text
from handlers.import_bulk import handle_import_document, handle_import_text
from handlers.team import handle_team_text
from handlers.habits import handle_habit_text, habit_skip
from handlers.custom_bot import handle_custom_bot_text
logger = logging.getLogger(__name__)
PAGE_SIZE = 10
PRIORITY_LABEL = {'high': '🔴 بالا', 'medium': '🟠 متوسط', 'low': '🟢 پایین'}
STATUS_LABEL = {'pending': '⏳ در انتظار', 'in_progress': '🚀 در حال انجام', 'done': '✅ انجام شده', 'cancelled': '❌ لغو شده'}
PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}

# NOTE: full handler restored from commit 8a5078...; subsequent sections remain unchanged.
