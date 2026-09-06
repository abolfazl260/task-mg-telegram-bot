"""Guest Mode support for creating quick tasks from Telegram chats."""
from __future__ import annotations
import asyncio, logging, re
from datetime import date, datetime, timedelta
from html import escape
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from handlers.business import handle_business_connection, handle_business_message, handle_deleted_business_messages, handle_edited_business_message
from services.groq_service import GroqConfigurationError, GroqRequestError, parse_task_request
from services.task_service import create_task, get_all_user_tasks
from utils.date_parse import parse_deadline_input
logger = logging.getLogger(__name__)
_ADD_WORDS=("add","task","todo","تسک","وظیفه","کار","ثبت","ایجاد")
_PRIORITY_WORDS={"high":("high","بالا","فوری","مهم","urgent","asap","ضروری","🔴"),"medium":("medium","متوسط","عادی","🟠"),"low":("low","پایین","کم","🟢")}
_PRIORITY_LABEL={"high":"🔴 بالا","medium":"🟠 متوسط","low":"🟢 پایین"}

def _guest_message(update): return (update.api_kwargs or {}).get("guest_message")
def _user_label(user):
    if not user:return "کاربر مهمان"
    first=(user.get("first_name") or "").strip(); last=(user.get("last_name") or "").strip(); username=(user.get("username") or "").strip()
    return (first+(" "+last if last else "")).strip() or (f"@{username}" if username else "کاربر مهمان")
def _extract_title(text,bot_username=""):
    title=(text or "").strip()
    if bot_username:title=re.sub(rf"@{re.escape(bot_username)}\b"," ",title,flags=re.I)
    title=re.sub(r"^/(add|task|todo)(?:@\w+)?\b"," ",title,flags=re.I).strip()
    for word in _ADD_WORDS:title=re.sub(rf"^(?:{re.escape(word)})[:：\-\s]+","",title,flags=re.I).strip()
    return title[:240]
def _extract_priority(text):
    lowered=(text or "").lower()
    for priority,words in _PRIORITY_WORDS.items():
        if any(word.lower() in lowered for word in words):return priority
    return "medium"
def _extract_deadline(text):
    value=text or ""
    for token in re.findall(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b",value):
        parsed=parse_deadline_input(token.replace("/","-"))
        if parsed:return parsed
    today=date.today()
    for pattern,offset in ((r"پس[‌\s]*فردا",2),(r"فردا",1),(r"امروز",0)):
        if re.search(pattern,value,flags=re.I):return (today+timedelta(days=offset)).isoformat()
    return ""
def _extract_fallback_tags(text):
    rules=[(r"خرید|بخر|فروشگاه|سفارش|تخم\s*مرغ|نان|مواد\s*غذایی","#خرید"),(r"جلسه|شرکت|مدیر|پروژه|گزارش|مشتری|قرارداد|اداری","#کاری"),(r"پرداخت|فاکتور|هزینه|پول|بودجه|حقوق|قبض|صورتحساب","#مالی"),(r"خانواده|خانه|شخصی|دوست|سفر|تفریح","#شخصی"),(r"ورزش|تمرین|دارو|پزشک|سلامت|خواب|پیاده\s*روی","#سلامت")]
    tags=[]
    for pattern,tag in rules:
        if re.search(pattern,text or "",flags=re.I) and tag not in tags:tags.append(tag)
        if len(tags)==2:break
    return ", ".join(tags)
def _limit_tags(value):
    raw=str(value or "").strip()
    if not raw:return ""
    unique=[]
    for item in [x.strip() for x in re.split(r"[,،\n]+",raw) if x.strip()]:
        if item not in unique:unique.append(item[:50])
        if len(unique)==2:break
    return ", ".join(unique)
def _extract_reply_text(guest):
    reply=guest.get("reply_to_message") or {}
    return (reply.get("text") or reply.get("caption") or "").strip() if isinstance(reply,dict) else ""
def _is_report_request(text):return any(word in (text or "").lower() for word in ("report","گزارش","status","وضعیت"))
def _build_guest_report(user_id):
    tasks=get_all_user_tasks(user_id)
    if not tasks:return "📊 گزارش مهم\n\nهنوز هیچ تسکی برای شما ثبت نشده است."
    active=[t for t in tasks if t.get("status") in ("pending","in_progress")]; overdue=[]; today=[]; today_date=date.today()
    for task in active:
        deadline=task.get("deadline") or ""
        try:
            due=parse_deadline_input(deadline) or deadline
            if not due:continue
            due_date=datetime.strptime(due,"%Y-%m-%d").date()
            if due_date<today_date:overdue.append(task)
            elif due_date==today_date:today.append(task)
        except Exception:continue
    high=[t for t in active if t.get("priority")=="high"]
    return "\n".join(["📊 گزارش مهم تسک‌ها","",f"📌 کل تسک‌ها: {len(tasks)}",f"⏳ فعال: {len(active)}",f"🔴 اولویت بالا: {len(high)}",f"⏰ موعد امروز: {len(today)}",f"🔻 عقب‌افتاده: {len(overdue)}"])
def _article_result(title,text):return {"type":"article","id":"guest-task-created","title":title[:64],"input_message_content":{"message_text":text,"parse_mode":ParseMode.HTML}}
async def _answer_guest_query(context,guest_query_id,text,title="ثبت تسک"):
    await context.bot._post("answerGuestQuery",data={"guest_query_id":guest_query_id,"result":_article_result(title,text)})
async def _analyze_guest_task(user_id,request_text):
    from services.task_intelligence import normalize_user_text
    normalized=normalize_user_text(request_text)
    if not normalized:raise GroqRequestError("متن درخواست خالی است.")
    try:return await asyncio.to_thread(parse_task_request,user_id,normalized)
    except (GroqConfigurationError,GroqRequestError):return {"action":"CREATE_TASK","title":normalized[:200],"deadline":_extract_deadline(normalized),"priority":_extract_priority(normalized),"category":"","tags":_extract_fallback_tags(normalized),"description":""}
async def handle_guest_task(update,context):
    if update.business_connection:await handle_business_connection(update,context);return
    if update.business_message:await handle_business_message(update,context);return
    if update.edited_business_message:await handle_edited_business_message(update,context);return
    if update.deleted_business_messages:await handle_deleted_business_messages(update,context);return
    guest=_guest_message(update)
    if not guest:return
    guest_query_id=guest.get("guest_query_id");caller=guest.get("from") or guest.get("guest_bot_caller_user") or {};user_id=caller.get("id");raw_text=guest.get("text") or guest.get("caption") or "";reply_text=_extract_reply_text(guest);chat=guest.get("chat") or {}
    if not guest_query_id:return
    if not user_id:await _answer_guest_query(context,guest_query_id,"⚠️ کاربر ارسال‌کننده قابل تشخیص نیست؛ تسک ثبت نشد.");return
    bot_username=(getattr(context.bot,"username",None) or "").strip()
    if _is_report_request(raw_text):await _answer_guest_query(context,guest_query_id,_build_guest_report(user_id),title="گزارش مهم");return
    title_text=_extract_title(raw_text,bot_username) or _extract_title(reply_text,"")
    if not title_text:await _answer_guest_query(context,guest_query_id,"برای ثبت تسک، بات را همراه عنوان صدا بزنید.");return
    ai_request=reply_text if reply_text and not _extract_title(raw_text,bot_username) else (f"{reply_text}\n\nدستور همراه Reply: {title_text}" if reply_text else title_text)
    try:draft=await _analyze_guest_task(user_id,ai_request)
    except Exception:draft={"action":"CREATE_TASK","title":title_text,"deadline":_extract_deadline(ai_request),"priority":_extract_priority(ai_request),"tags":_extract_fallback_tags(ai_request)}
    title=str(draft.get("title") or title_text).strip()[:240];priority=draft.get("priority") if draft.get("priority") in {"high","medium","low"} else _extract_priority(ai_request);deadline=str(draft.get("deadline") or "").strip() or _extract_deadline(ai_request);tags=_limit_tags(draft.get("tags")) or _extract_fallback_tags(ai_request);description=reply_text[:2000] if reply_text else ""
    task_id=create_task(user_id=user_id,title=title,priority=priority,deadline=deadline,category="",tags=tags,description=description)
    await _answer_guest_query(context,guest_query_id,"<b>✅ تسک با موفقیت ثبت شد</b>\n" f"<b>🆔 شماره تسک:</b> <code>#{escape(str(task_id))}</code>\n\n" f"<b>📌 عنوان</b>\n{escape(title)}\n\n" f"<b>📝 توضیحات</b>\n{escape(reply_text[:2000]) if reply_text else '—'}\n\n" f"<b>🎯 اولویت:</b> {_PRIORITY_LABEL[priority]}\n" f"<b>⏰ موعد:</b> {escape(deadline or 'بدون ددلاین')}\n" f"<b>🏷️ تگ‌ها:</b> {escape(tags or 'بدون تگ')}\n" f"<b>📂 دسته‌بندی:</b> بدون دسته‌بندی\n" f"<b>📊 وضعیت:</b> ⏳ در انتظار انجام",title=f"تسک #{escape(str(task_id))}")
