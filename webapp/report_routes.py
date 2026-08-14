"""Private web-report routes and Telegram report links.

The monthly report is a normal HTTP page, intentionally NOT a Telegram Web App.
The URL contains only an opaque, non-guessable report token.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, quote, urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot_context import get_current_bot_key
from .api import authenticate_telegram_request
from .config import WEBAPP_BASE_URL
from .report_tokens import build_report_url, create_report_token
from .reports import monthly_report
from services.calendar_runtime_extensions import viewer_id


def _json(handler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html(handler, status: int, body: str) -> None:
    encoded = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


_REPORT_PAGE = r'''<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0f172a"><title>گزارش تحت وب</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Vazirmatn,Tahoma,system-ui,sans-serif;background:linear-gradient(135deg,#f8fafc,#eef2ff);color:#172033}
main{max-width:1280px;margin:auto;padding:22px}.hero{background:linear-gradient(135deg,#0f172a,#263653);color:#fff;border-radius:28px;padding:28px;box-shadow:0 18px 50px #0f172a22;overflow:hidden}
.hero h1{margin:0 0 8px;font-size:30px}.hero p{margin:0;color:#cbd5e1}.hero-top{display:flex;justify-content:space-between;gap:20px;align-items:center}.badge{background:#ffffff14;border:1px solid #ffffff20;border-radius:999px;padding:9px 13px;font-size:13px}
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:18px}.stat{background:#ffffff0d;border:1px solid #ffffff14;border-radius:18px;padding:15px}.stat strong{display:block;font-size:25px;margin-bottom:4px}.stat span{font-size:12px;color:#cbd5e1}
.card{background:#fff;border:1px solid #e8edf5;border-radius:22px;padding:20px;margin-top:16px;box-shadow:0 10px 30px #1720330a}.section-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.section-title h2{margin:0;font-size:19px}.muted{color:#718096;font-size:13px}
.toolbar{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}button{border:1px solid #e5eaf2;background:#f8fafc;color:#243044;border-radius:15px;padding:13px 12px;cursor:pointer;font:inherit;font-weight:600;transition:.18s}button:hover{transform:translateY(-1px);background:#fff}button.active{background:#172033;color:#fff;border-color:#172033}
.summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.summary-box{background:#f8fafc;border-radius:17px;padding:15px}.summary-box h3{margin:0 0 10px;font-size:15px}.summary-row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #edf1f6;font-size:13px}.summary-row:last-child{border:0}
.table-wrap{overflow:auto;border:1px solid #edf1f6;border-radius:16px}table{width:100%;border-collapse:collapse;min-width:700px}th{background:#f8fafc;color:#667085;font-size:12px}td,th{padding:12px;text-align:right;border-bottom:1px solid #edf1f6}tbody tr:hover{background:#fafcff}.chip{display:inline-flex;padding:5px 9px;border-radius:999px;background:#f1f5f9;font-size:12px}.error{color:#b42318;background:#fff4f2;padding:12px;border-radius:12px}.loading{padding:22px;text-align:center;color:#718096}
.week-grid{display:grid;grid-template-columns:repeat(7,minmax(300px,1fr));gap:14px;overflow-x:auto;padding-bottom:8px}.week-day{background:#f8fafc;border:1px solid #e5eaf2;border-radius:20px;min-width:300px;overflow:hidden}.week-day.today{border:2px solid #172033}.day-head{padding:16px;background:linear-gradient(135deg,#f8fafc,#eef2f7);border-bottom:1px solid #e5eaf2}.today .day-head{background:linear-gradient(135deg,#172033,#344767);color:#fff}.day-title{font-size:17px;font-weight:800}.day-date{font-size:12px;margin-top:5px;color:#718096}.today .day-date{color:#d5dbea}.day-count{display:inline-flex;margin-top:9px;padding:5px 9px;border-radius:999px;background:#fff;border:1px solid #e5eaf2;font-size:11px;font-weight:700}.today .day-count{background:#ffffff18;border-color:#ffffff30;color:#fff}.week-table{width:100%;min-width:0;border-collapse:collapse}.week-table th{font-size:10px;padding:9px 7px}.week-table td{font-size:11px;padding:10px 7px}.week-table .row-no{width:28px;text-align:center;color:#98a2b3}.week-task{font-weight:700;line-height:1.5}.week-assignee{font-size:10px;color:#667085;margin-top:4px}.today .week-assignee{color:#718096}.priority{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;font-size:10px;font-weight:700}.priority:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.priority-high{color:#b42318;background:#fff1f0}.priority-medium{color:#b54708;background:#fff7e8}.priority-low{color:#027a48;background:#ecfdf3}.empty-day{padding:30px 15px;text-align:center;color:#98a2b3;font-size:12px}.week-note{margin-top:12px;font-size:12px;color:#718096}
@media(max-width:1100px){.stats{grid-template-columns:repeat(3,1fr)}.toolbar{grid-template-columns:repeat(2,1fr)}.summary-grid{grid-template-columns:1fr}.week-grid{grid-template-columns:repeat(7,minmax(280px,1fr))}}
@media(max-width:560px){main{padding:12px}.hero{padding:20px;border-radius:22px}.hero-top{display:block}.badge{display:inline-block;margin-top:14px}.stats{grid-template-columns:repeat(2,1fr)}.toolbar{grid-template-columns:1fr 1fr}.week-grid{grid-template-columns:1fr;overflow-x:visible}.week-day{min-width:0}}
</style></head>
<body><main>
<section id="app" class="hero"><div class="loading">در حال بارگذاری گزارش...</div></section>
<section class="card"><div class="section-title"><div><h2>گزارش‌های قابل مشاهده</h2></div></div>
<div class="toolbar"><button data-section="tasks">📋 جدول وظایف</button><button data-section="week">📅 برنامه هفته</button><button data-section="kanban">🧩 کانبان</button><button data-section="calendar">📅 تقویم</button><button data-section="deadlines">⏰ مهلت‌ها</button><button data-section="status">📌 وضعیت‌ها</button><button data-section="priority">🚦 اولویت‌ها</button><button data-section="categories">🗂 دسته‌بندی‌ها</button><button data-section="habits">🌱 گزارش عادت‌ها</button></div></section>
<section id="details" class="card"><div class="loading">برای مشاهده جزئیات یکی از گزارش‌ها را انتخاب کنید.</div></section>
</main><script>
const token=__REPORT_TOKEN__;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const app=document.getElementById('app'),details=document.getElementById('details');
async function getJson(url){const r=await fetch(url,{cache:'no-store'});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.error==='report_not_found'?'لینک گزارش معتبر نیست یا منقضی شده است.':'خطا در دریافت اطلاعات');return d}
function stat(v,l){return `<div class="stat"><strong>${v}</strong><span>${l}</span></div>`}
function rows(items){return(items||[]).map(x=>`<div class="summary-row"><span>${esc(x.label)}</span><b>${x.count}</b></div>`).join('')||'<div class="muted">داده‌ای وجود ندارد.</div>'}
function priority(p){const k=(p||'').toLowerCase();const c=k==='high'?'priority-high':k==='low'?'priority-low':'priority-medium';return `<span class="priority ${c}">${esc(p||'نامشخص')}</span>`}
async function loadSummary(){try{const d=await getJson('/api/public-reports/monthly/'+encodeURIComponent(token));const s=d.summary||{};app.innerHTML=`<div class="hero-top"><div><h1>📊 گزارش تحت وب</h1><p>${esc(d.period?.gregorian||'')} · ${esc(d.period?.jalali||'')}</p></div><div class="badge">گزارش شخصی و اختصاصی</div></div><div class="stats">${stat(s.total||0,'کل وظایف')}${stat(s.done||0,'انجام‌شده')}${stat(s.in_progress||0,'در حال انجام')}${stat(s.pending||0,'شروع‌نشده')}${stat(s.cancelled||0,'لغوشده')}${stat((s.completion_rate||0)+'٪','نرخ انجام')}${stat(s.overdue||0,'عقب‌افتاده')}${stat(s.with_deadline||0,'دارای مهلت')}${stat(s.without_deadline||0,'بدون مهلت')}</div>`;details.insertAdjacentHTML('beforebegin',`<section id="summary-extra" class="card"><div class="summary-grid"><div class="summary-box"><h3>📌 وضعیت‌ها</h3>${rows(d.by_status)}</div><div class="summary-box"><h3>🚦 اولویت‌ها</h3>${rows(d.by_priority)}</div><div class="summary-box"><h3>🗂 دسته‌بندی‌ها</h3>${rows((d.by_category||[]).slice(0,12))}</div></div></section>`)}catch(e){app.innerHTML='<h1>گزارش تحت وب</h1><p class="error">'+esc(e.message)+'</p>'}}
function renderWeek(d){const days=d.week?.days||[];const html=`<div class="section-title"><div><h2>📅 برنامه هفته</h2><div class="muted">بر اساس مهلت انجام وظایف · ${esc(d.week?.start||'')} تا ${esc(d.week?.end||'')}</div></div><span class="chip">${d.week?.total||0} وظیفه</span></div><div class="week-grid">${days.map((day,index)=>`<article class="week-day ${index===0?'today':''}"><div class="day-head"><div class="day-title">${esc(day.label)}</div><div class="day-date">${esc(day.jalali)} · ${esc(day.date)}</div><span class="day-count">${day.count||0} وظیفه</span></div>${day.rows?.length?`<div class="table-wrap" style="border:0;border-radius:0"><table class="week-table"><thead><tr><th class="row-no">#</th><th>وظیفه</th><th>زمان</th><th>اولویت</th></tr></thead><tbody>${day.rows.map((x,i)=>{const raw=String(x.deadline||'');const time=raw.includes('T')?raw.split('T')[1].slice(0,5):(raw.length>10?raw.slice(11,16):'—');return `<tr><td class="row-no">${i+1}</td><td><div class="week-task">${esc(x.title)}</div><div class="week-assignee">👤 ${esc(x.assignee||'بدون مسئول')}</div></td><td>${esc(time)}</td><td>${priority(x.priority)}</td></tr>`}).join('')}</tbody></table></div>`:'<div class="empty-day">برای این روز وظیفه‌ای ثبت نشده است.</div>'}</article>`).join('')}</div><div class="week-note">زمان‌بندی بر اساس مهلت انجام وظایف است و مسئول هر وظیفه نیز در همان ردیف نمایش داده می‌شود.</div>`;details.innerHTML=html}
function card(x){return `<div class="task"><b>${esc(x.title)}</b><span class="chip">${esc(x.status_label)}</span> <span class="chip">${esc(x.priority_label)}</span>${x.deadline?`<div class="muted" style="margin-top:7px">⏰ ${esc(x.deadline)}</div>`:''}${x.category?`<div class="muted">🗂 ${esc(x.category)}</div>`:''}${x.assignee?`<div class="muted">👤 ${esc(x.assignee)}</div>`:''}</div>`}
async function loadSection(section){details.innerHTML='<div class="loading">در حال دریافت گزارش...</div>';document.querySelectorAll('[data-section]').forEach(b=>b.classList.toggle('active',b.dataset.section===section));try{const d=await getJson('/api/public-reports/monthly/'+encodeURIComponent(token)+'?section='+encodeURIComponent(section));if(section==='week'){renderWeek(d);return}if(section==='kanban'){const labels={pending:'شروع‌نشده',in_progress:'در حال انجام',done:'انجام‌شده',cancelled:'لغو شده',canceled:'لغو شده'};details.innerHTML=`<div class="section-title"><h2>🧩 کانبان</h2><span class="muted">${d.total||0} مورد</span></div><div class="board">${Object.entries(labels).map(([k,l])=>`<div class="column"><h3>${l}</h3>${(d.columns?.[k]||[]).map(card).join('')||'<p class="muted">موردی نیست</p>'}</div>`).join('')}</div>`;return}if(section==='calendar'){details.innerHTML=`<div class="section-title"><h2>📅 تقویم</h2></div><div class="table-wrap"><table><thead><tr><th>تاریخ</th><th>عنوان</th><th>وضعیت</th><th>اولویت</th></tr></thead><tbody>${d.rows?.length?d.rows.map(x=>`<tr><td>${esc(x.deadline)}</td><td>${esc(x.title)}</td><td>${esc(x.status_label)}</td><td>${esc(x.priority_label)}</td></tr>`).join(''):'<tr><td colspan="4">موردی نیست.</td></tr>'}</tbody></table></div>`;return}if(section==='habits'){const h=d.habits||{};details.innerHTML=`<div class="section-title"><h2>🌱 گزارش عادت‌ها</h2></div><div class="summary-grid"><div class="summary-box"><h3>عادت فعال</h3><b>${h.active_habits||0}</b></div><div class="summary-box"><h3>ثبت موفق در ماه</h3><b>${h.completed_logs||0}</b></div><div class="summary-box"><h3>روز دارای فعالیت</h3><b>${h.completion_days||0}</b></div></div><div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>ردیف</th><th>عادت</th><th>دسته‌بندی</th><th>هدف</th><th>تکرار</th><th>تعداد انجام</th><th>آخرین انجام</th></tr></thead><tbody>${(h.rows||[]).map((x,i)=>`<tr><td>${i+1}</td><td><b>${esc(x.title)}</b></td><td>${esc(x.category)}</td><td>${esc(x.target)}</td><td>${esc(x.repeat_type)}</td><td>${x.completed}</td><td>${esc(x.last_done)}</td></tr>`).join('')||'<tr><td colspan="7">در این ماه عادتی ثبت نشده است.</td></tr>'}</tbody></table></div>`;return}const rows=d.rows||[];details.innerHTML=`<div class="section-title"><h2>گزارش جزئیات</h2><span class="muted">${d.total||rows.length||0} مورد</span></div><div class="table-wrap"><table><thead><tr><th>ردیف</th><th>عنوان</th><th>وضعیت</th><th>اولویت</th><th>مهلت</th><th>دسته‌بندی</th><th>مسئول</th></tr></thead><tbody>${rows.length?rows.map((x,i)=>`<tr><td>${i+1}</td><td><b>${esc(x.title||x.category||x.status||x.priority||'')}</b></td><td>${esc(x.status_label||x.status||'—')}</td><td>${esc(x.priority_label||x.priority||'—')}</td><td>${esc(x.deadline||'—')}</td><td>${esc(x.category||'—')}</td><td>${esc(x.assignee||'بدون مسئول')}</td></tr>`).join(''):'<tr><td colspan="7">موردی پیدا نشد.</td></tr>'}</tbody></table></div>`}catch(e){details.innerHTML='<p class="error">'+esc(e.message)+'</p>'}}
document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',()=>loadSection(b.dataset.section)));loadSummary();
</script></body></html>'''


def web_report_html(token: str) -> str:
    return _REPORT_PAGE.replace('__REPORT_TOKEN__', json.dumps(token, ensure_ascii=False))


def handle_report_get(handler) -> bool:
    path = urlparse(handler.path).path
    if path and path != "/" and not path.startswith("/api/") and path != "/report-launch":
        token = quote(path.strip("/"), safe="")
        if "/" not in token and len(token) >= 40:
            _html(handler, 200, web_report_html(token))
            return True
    if path == "/report-launch":
        _html(handler, 400, "<h2>این مسیر دیگر استفاده نمی‌شود.</h2><p>گزارش از لینک اختصاصی باز می‌شود.</p>")
        return True
    return False


def handle_report_api(handler) -> bool:
    parsed = urlparse(handler.path)
    path = parsed.path
    if path == "/api/report-token" and handler.command == "GET":
        query = parse_qs(parsed.query)
        report_type = (query.get("type") or ["monthly"])[0]
        bot_key = (query.get("bot_key") or [""])[0].strip()
        if report_type != "monthly" or not bot_key:
            _json(handler, 400, {"error": "invalid_report_request"})
            return True
        try:
            user = authenticate_telegram_request(handler.headers.get("X-Telegram-Init-Data", ""), bot_key)
        except Exception:
            _json(handler, 401, {"error": "unauthorized"})
            return True
        token = create_report_token(get_current_bot_key(), str(user.id), report_type)
        _json(handler, 200, {"url": build_report_url(WEBAPP_BASE_URL, token), "expires_in_days": 30})
        return True

    prefix = "/api/public-reports/monthly/"
    if path.startswith(prefix) and handler.command == "GET":
        token = path[len(prefix):].strip("/")
        section = (parse_qs(parsed.query).get("section") or ["summary"])[0]
        allowed = {"summary", "tasks", "week", "kanban", "calendar", "deadlines", "categories", "category", "status", "priority", "habits", "heatmap", "activity"}
        if section not in allowed or not token or "/" in token:
            _json(handler, 404, {"error": "report_not_found"})
            return True
        try:
            data = monthly_report(token, section=section)
        except Exception:
            _json(handler, 500, {"error": "report_generation_failed"})
            return True
        if data is None:
            _json(handler, 404, {"error": "report_not_found"})
        else:
            _json(handler, 200, data)
        return True
    return False


def add_monthly_web_button(markup: InlineKeyboardMarkup, user_id=None) -> InlineKeyboardMarkup:
    if user_id is None:
        user_id = viewer_id()
    if not user_id:
        return markup
    token = create_report_token(get_current_bot_key(), str(user_id), "monthly")
    url = build_report_url(WEBAPP_BASE_URL, token)
    rows = [list(row) for row in markup.inline_keyboard]
    if not any(button.text == "📊 گزارش ماهانه تحت وب" for row in rows for button in row):
        rows.insert(0, [InlineKeyboardButton("📊 گزارش ماهانه تحت وب", url=url)])
    return InlineKeyboardMarkup(rows)
