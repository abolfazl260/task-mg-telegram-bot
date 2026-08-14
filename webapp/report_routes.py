"""Private HTTP reporting website. This is intentionally NOT a Telegram Web App."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, quote, urlparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot_context import get_current_bot_key
from .api import authenticate_telegram_request
from .config import WEBAPP_BASE_URL
from .report_tokens import build_report_url, create_report_token
from .reports import monthly_report, report_section
from services.calendar_runtime_extensions import viewer_id


def _json(handler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status); handler.send_header("Content-Type", "application/json; charset=utf-8"); handler.send_header("Cache-Control", "no-store"); handler.send_header("Content-Length", str(len(body))); handler.end_headers(); handler.wfile.write(body)


def _html(handler, status: int, body: str) -> None:
    encoded = body.encode("utf-8")
    handler.send_response(status); handler.send_header("Content-Type", "text/html; charset=utf-8"); handler.send_header("Cache-Control", "no-store"); handler.send_header("Content-Length", str(len(encoded))); handler.end_headers(); handler.wfile.write(encoded)


def web_report_html(token: str) -> str:
    safe = json.dumps(token, ensure_ascii=False)
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>گزارش تحت وب</title><style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#f5f7fb;margin:0;color:#172033}}main{{max-width:1180px;margin:18px auto;padding:10px}}.card{{background:#fff;border-radius:18px;padding:18px;margin:10px 0;box-shadow:0 4px 18px #0000000d}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:10px}}.metric{{font-size:27px;font-weight:750}}.muted{{color:#687386}}.toolbar{{display:flex;flex-wrap:wrap;gap:6px}}button{{border:0;border-radius:12px;padding:11px 14px;cursor:pointer;font:inherit;background:#eef2f7}}button.active{{background:#172033;color:#fff}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #edf0f5;text-align:right}}.table-wrap{{overflow:auto}}.error{{color:#b42318}}.board{{display:grid;grid-template-columns:repeat(4,minmax(220px,1fr));gap:10px;overflow:auto}}.column{{background:#f4f6fa;border-radius:16px;padding:10px;min-height:180px}}.column h3{{margin-top:4px}}.task{{background:#fff;border-radius:12px;padding:10px;margin:8px 0;box-shadow:0 2px 8px #0000000a}}.pager{{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:12px}}@media(max-width:800px){{.board{{grid-template-columns:1fr 1fr}}}}@media(max-width:520px){{.board{{grid-template-columns:1fr}}}}
</style></head><body><main><div id="app" class="card">در حال بارگذاری گزارش...</div><div class="card"><h2>بخش‌های گزارش</h2><p class="muted">فقط خلاصه در شروع بارگذاری می‌شود. جزئیات هر بخش تنها بعد از انتخاب شما از دیتابیس دریافت می‌شود.</p><div class="toolbar"><button data-section="tasks">📋 جدول وظایف</button><button data-section="kanban">🧩 کانبان</button><button data-section="calendar">📅 تقویم</button><button data-section="deadlines">⏰ مهلت‌ها</button><button data-section="status">📌 وضعیت‌ها</button><button data-section="priority">🚦 اولویت‌ها</button><button data-section="category">🗂 دسته‌بندی‌ها</button></div><div id="table"></div></div></main><script>
const token={safe}; const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const app=document.getElementById('app'), table=document.getElementById('table');
async function getJson(url){{const r=await fetch(url,{{cache:'no-store'}});const d=await r.json();if(!r.ok)throw new Error(d.error==='report_not_found'?'لینک گزارش معتبر نیست یا منقضی شده است.':'خطا در دریافت اطلاعات');return d;}}
function metric(v,l){{return `<div class="card"><div class="metric">${{v}}</div>${{l}}</div>`}}
async function loadSummary(){{try{{const d=await getJson('/api/public-reports/monthly/'+encodeURIComponent(token));const s=d.summary;app.innerHTML=`<h1>📊 گزارش تحت وب</h1><p class="muted">بازه گزارش: ${{esc(d.period.jalali)}} · ${{esc(d.period.gregorian)}}</p><div class="grid">${{metric(s.total,'کل وظایف')}}${{metric(s.done,'انجام‌شده')}}${{metric(s.in_progress,'در حال انجام')}}${{metric(s.pending,'شروع‌نشده')}}${{metric(s.cancelled,'لغوشده')}}${{metric(s.completion_rate+'٪','نرخ انجام')}}${{metric(s.overdue,'عقب‌افتاده')}}${{metric(s.with_deadline,'دارای مهلت')}}${{metric(s.without_deadline,'بدون مهلت')}}</div><div class="grid"><div class="card"><h3>وضعیت‌ها</h3>${{d.by_status.map(x=>`<p>${{esc(x.label)}}: <b>${{x.count}}</b></p>`).join('')}}</div><div class="card"><h3>اولویت‌ها</h3>${{d.by_priority.map(x=>`<p>${{esc(x.label)}}: <b>${{x.count}}</b></p>`).join('')}}</div><div class="card"><h3>دسته‌بندی‌ها</h3>${{d.by_category.slice(0,10).map(x=>`<p>${{esc(x.label)}}: <b>${{x.count}}</b></p>`).join('')}}</div></div>`}}catch(e){{app.innerHTML='<h1>گزارش تحت وب</h1><p class="error">'+esc(e.message)+'</p>'}}}}
function card(x){{return `<div class="task"><b>${{esc(x.title)}}</b><div class="muted">${{esc(x.status_label)}} · ${{esc(x.priority_label)}}</div>${{x.deadline?`<div>⏰ ${{esc(x.deadline)}}</div>`:''}}${{x.category?`<div>🗂 ${{esc(x.category)}}</div>`:''}}</div>`}}
async function loadSection(section,page=1){{table.innerHTML='<p class="muted">در حال دریافت بخش انتخاب‌شده...</p>';document.querySelectorAll('[data-section]').forEach(b=>b.classList.toggle('active',b.dataset.section===section));try{{const d=await getJson('/api/public-reports/monthly/'+encodeURIComponent(token)+'/section/'+encodeURIComponent(section)+'?page='+page);if(section==='kanban'){{const labels={{pending:'شروع‌نشده',in_progress:'در حال انجام',done:'انجام‌شده',cancelled:'لغو شده'}};table.innerHTML=`<div class="board">${{Object.entries(labels).map(([k,l])=>`<div class="column"><h3>${{l}}</h3>${{(d.columns[k]||[]).map(card).join('')||'<p class="muted">موردی نیست</p>'}}</div>`).join('')}}</div>${{d.limited?'<p class="muted">برای جلوگیری از فشار، حداکثر ۲۰۰ کارت در نمای کانبان نمایش داده شده است.</p>':''}}`;return}}if(section==='calendar'){{table.innerHTML=`<h3>تقویم مهلت‌ها</h3><div class="table-wrap"><table><thead><tr><th>تاریخ</th><th>عنوان</th><th>وضعیت</th><th>اولویت</th></tr></thead><tbody>${{d.rows.length?d.rows.map(x=>`<tr><td>${{esc(x.deadline)}}</td><td>${{esc(x.title)}}</td><td>${{esc(x.status_label)}}</td><td>${{esc(x.priority_label)}}</td></tr>`).join(''):'<tr><td colspan="4">موردی نیست.</td></tr>'}}</tbody></table></div>`;return}}table.innerHTML=`<div class="table-wrap"><table><thead><tr><th>شناسه</th><th>عنوان</th><th>وضعیت</th><th>اولویت</th><th>مهلت</th><th>دسته‌بندی</th></tr></thead><tbody>${{d.rows.length?d.rows.map(x=>`<tr><td>${{esc(x.id)}}</td><td>${{esc(x.title)}}</td><td>${{esc(x.status_label)}}</td><td>${{esc(x.priority_label)}}</td><td>${{esc(x.deadline||'—')}}</td><td>${{esc(x.category||'—')}}</td></tr>`).join(''):'<tr><td colspan="6">موردی پیدا نشد.</td></tr>'}}</tbody></table></div><div class="pager">${{d.page>1?`<button onclick="loadSection('${{section}}',${{d.page-1}})">قبلی</button>`:''}}<span>صفحه ${{d.page}} از ${{d.pages}} · ${{d.total}} مورد</span>${{d.page<d.pages?`<button onclick="loadSection('${{section}}',${{d.page+1}})">بعدی</button>`:''}}</div>`}}catch(e){{table.innerHTML='<p class="error">'+esc(e.message)+'</p>'}}}}
document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',()=>loadSection(b.dataset.section,1)));loadSummary();
</script></body></html>'''


def handle_report_get(handler) -> bool:
    path = urlparse(handler.path).path
    if path and path != "/" and not path.startswith("/api/") and path != "/report-launch":
        token = quote(path.strip("/"), safe="")
        if "/" not in token and len(token) >= 40:
            _html(handler, 200, web_report_html(token)); return True
    if path == "/report-launch":
        _html(handler, 400, "<h2>این مسیر دیگر استفاده نمی‌شود.</h2><p>گزارش از لینک اختصاصی باز می‌شود.</p>"); return True
    return False


def handle_report_api(handler) -> bool:
    parsed = urlparse(handler.path); path = parsed.path
    if path == "/api/report-token" and handler.command == "GET":
        query=parse_qs(parsed.query); report_type=(query.get("type") or ["monthly"])[0]; bot_key=(query.get("bot_key") or [""])[0].strip()
        if report_type != "monthly" or not bot_key: _json(handler,400,{"error":"invalid_report_request"}); return True
        try: user=authenticate_telegram_request(handler.headers.get("X-Telegram-Init-Data",""),bot_key)
        except Exception: _json(handler,401,{"error":"unauthorized"}); return True
        token=create_report_token(bot_key,str(user.id),report_type); _json(handler,200,{"url":build_report_url(WEBAPP_BASE_URL,token),"expires_in_days":30}); return True
    prefix="/api/public-reports/monthly/"
    if path.startswith(prefix) and handler.command == "GET":
        rest=path[len(prefix):].strip("/"); parts=rest.split("/",1); token=parts[0]
        if not token or len(token)<40: _json(handler,404,{"error":"report_not_found"}); return True
        try:
            if len(parts)==2 and parts[1].startswith("section/"):
                section=parts[1][8:]; q=parse_qs(parsed.query); page=int((q.get("page") or ["1"])[0]); data=report_section(token,section,page)
            else: data=monthly_report(token)
        except Exception: _json(handler,500,{"error":"report_generation_failed"}); return True
        if data is None: _json(handler,404,{"error":"report_not_found"})
        elif data.get("error"): _json(handler,400,data)
        else: _json(handler,200,data)
        return True
    return False


def add_monthly_web_button(markup: InlineKeyboardMarkup, user_id=None) -> InlineKeyboardMarkup:
    """Normal HTTP URL button; intentionally NOT Telegram Web App."""
    if user_id is None: user_id=viewer_id()
    if not user_id:return markup
    token=create_report_token(get_current_bot_key(),str(user_id),"monthly"); url=build_report_url(WEBAPP_BASE_URL,token)
    rows=[list(row) for row in markup.inline_keyboard]
    if not any(button.text=="📊 گزارش تحت وب" for row in rows for button in row): rows.insert(0,[InlineKeyboardButton("📊 گزارش تحت وب",url=url)])
    return InlineKeyboardMarkup(rows)
