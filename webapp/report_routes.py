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


def monthly_report_html(token: str) -> str:
    safe_token = json.dumps(token, ensure_ascii=False)
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>گزارش ماهانه</title><style>
*{{box-sizing:border-box}}body{{font-family:system-ui,-apple-system,sans-serif;background:#f3f6fa;margin:0;color:#172033}}main{{max-width:1180px;margin:0 auto;padding:20px}}.hero{{background:linear-gradient(135deg,#172033,#344767);color:#fff;border-radius:24px;padding:26px;margin-bottom:16px}}.hero h1{{margin:0 0 8px;font-size:28px}}.muted{{color:#687386}}.hero .muted{{color:#d5dbea}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card{{background:#fff;border-radius:18px;padding:18px;margin:12px 0;box-shadow:0 3px 16px #0000000b}}.metric{{font-size:30px;font-weight:800}}.label{{font-size:13px;color:#687386;margin-top:4px}}.mini{{font-size:12px;color:#687386}}.section-title{{display:flex;align-items:center;justify-content:space-between;gap:10px}}.buttons{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}button{{border:0;border-radius:12px;padding:11px 14px;background:#eef2f7;color:#172033;cursor:pointer;font-family:inherit}}button:hover{{background:#dfe6ef}}button.active{{background:#172033;color:#fff}}table{{width:100%;border-collapse:collapse;background:#fff}}td,th{{padding:11px;border-bottom:1px solid #edf0f5;text-align:right}}th{{font-size:13px;color:#687386}}.table-wrap{{overflow:auto;border-radius:14px}}.error{{color:#b42318}}.hidden{{display:none}}.pill{{display:inline-block;padding:4px 9px;border-radius:20px;background:#eef2f7;font-size:12px}}@media(max-width:800px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:480px){{main{{padding:10px}}.grid{{grid-template-columns:1fr 1fr}}.metric{{font-size:24px}}}}
</style></head><body><main><section class="hero"><h1>📊 گزارش کامل ماهانه</h1><div id="period">در حال بارگذاری...</div><div class="mini" id="loaded"></div></section><section class="grid" id="metrics"></section><section class="card"><div class="section-title"><h2>نمای کلی</h2><span class="pill">گزارش ماه جاری</span></div><div id="breakdowns"></div></section><section class="card"><div class="section-title"><h2>گزارش‌های تفصیلی</h2><span class="mini">فقط هنگام انتخاب بارگذاری می‌شوند</span></div><div class="buttons"><button data-section="tasks">📋 همه وظایف</button><button data-section="deadlines">⏰ مهلت‌ها</button><button data-section="categories">🗂 دسته‌بندی‌ها</button><button data-section="status">📌 وضعیت‌ها</button><button data-section="priority">🚦 اولویت‌ها</button></div><div id="table-area" class="hidden"></div></section><div id="error" class="card error hidden"></div></main><script>
const token={safe_token};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const app=document.getElementById('metrics'); const breakdowns=document.getElementById('breakdowns');
async function getData(section='summary'){{const r=await fetch('/api/public-reports/monthly/'+encodeURIComponent(token)+(section!=='summary'?'?section='+encodeURIComponent(section):''),{{cache:'no-store'}});const d=await r.json();if(!r.ok)throw new Error(d.error==='report_not_found'?'لینک گزارش معتبر نیست یا منقضی شده است.':'دریافت گزارش با خطا مواجه شد.');return d}}
function metric(value,label){{return `<div class="card"><div class="metric">${{esc(value)}}</div><div class="label">${{esc(label)}}</div></div>`}}
function list(title,items,labelKey){{return `<div style="margin-top:14px"><b>${{esc(title)}}</b>${{items.length?items.map(x=>`<p style="margin:9px 0">${{esc(x[labelKey]||x.label)}} <strong>${{esc(x.count)}}</strong></p>`).join(''):'<p class="muted">اطلاعاتی وجود ندارد.</p>'}}</div>`}}
function renderSummary(d){{const s=d.summary;document.getElementById('period').innerHTML=esc(d.period.jalali)+' · '+esc(d.period.gregorian);document.getElementById('loaded').textContent='این اطلاعات فقط برای صاحب این لینک محاسبه شده است.';app.innerHTML=metric(s.total,'کل وظایف')+metric(s.done,'انجام‌شده')+metric(s.in_progress,'در حال انجام')+metric(s.pending,'شروع‌نشده')+metric(s.cancelled,'لغو شده')+metric(s.active,'فعال')+metric(s.overdue,'عقب‌افتاده')+metric(s.completion_rate+'٪','نرخ انجام')+metric(s.with_deadline,'دارای مهلت')+metric(s.without_deadline,'بدون مهلت')+metric(s.average_completed_per_day,'میانگین انجام روزانه');breakdowns.innerHTML=list('وضعیت‌ها',d.by_status,'label')+list('اولویت‌ها',d.by_priority,'label')+list('دسته‌بندی‌ها',d.by_category,'label')}}
function renderRows(section,d){{const rows=d.rows||[];let html='';if(section==='tasks')html=`<h3>همه وظایف (${{rows.length}})</h3><div class="table-wrap"><table><thead><tr><th>عنوان</th><th>وضعیت</th><th>اولویت</th><th>مهلت</th><th>دسته‌بندی</th></tr></thead><tbody>${{rows.map(x=>`<tr><td>${{esc(x.title)}}</td><td>${{esc(x.status_label)}}</td><td>${{esc(x.priority_label)}}</td><td>${{esc(x.deadline||'—')}}</td><td>${{esc(x.category||'—')}}</td></tr>`).join('')}}</tbody></table></div>`;else if(section==='deadlines')html=`<h3>وظایف دارای مهلت (${{rows.length}})</h3><div class="table-wrap"><table><thead><tr><th>عنوان</th><th>مهلت</th><th>وضعیت</th><th>اولویت</th></tr></thead><tbody>${{rows.map(x=>`<tr><td>${{esc(x.title)}}</td><td>${{esc(x.deadline)}}</td><td>${{esc(x.status_label)}}</td><td>${{esc(x.priority_label)}}</td></tr>`).join('')}}</tbody></table></div>`;else if(section==='categories')html=`<h3>دسته‌بندی‌ها</h3><div class="table-wrap"><table><thead><tr><th>دسته‌بندی</th><th>تعداد</th></tr></thead><tbody>${{rows.map(x=>`<tr><td>${{esc(x.category)}}</td><td>${{esc(x.count)}}</td></tr>`).join('')}}</tbody></table></div>`;else if(section==='status')html=`<h3>وضعیت‌ها</h3><div class="table-wrap"><table><thead><tr><th>وضعیت</th><th>تعداد</th></tr></thead><tbody>${{rows.map(x=>`<tr><td>${{esc(x.status)}}</td><td>${{esc(x.count)}}</td></tr>`).join('')}}</tbody></table></div>`;else html=`<h3>اولویت‌ها</h3><div class="table-wrap"><table><thead><tr><th>اولویت</th><th>تعداد</th></tr></thead><tbody>${{rows.map(x=>`<tr><td>${{esc(x.priority)}}</td><td>${{esc(x.count)}}</td></tr>`).join('')}}</tbody></table></div>`;const area=document.getElementById('table-area');area.innerHTML=html;area.classList.remove('hidden')}
async function load(){{try{{renderSummary(await getData())}}catch(e){{const er=document.getElementById('error');er.textContent=e.message;er.classList.remove('hidden')}}}}
document.querySelectorAll('button[data-section]').forEach(btn=>btn.addEventListener('click',async()=>{{document.querySelectorAll('button[data-section]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');const area=document.getElementById('table-area');area.classList.remove('hidden');area.innerHTML='<p>در حال دریافت اطلاعات...</p>';try{{renderRows(btn.dataset.section,await getData(btn.dataset.section))}}catch(e){{area.innerHTML='<p class="error">'+esc(e.message)+'</p>'}}}}));load();
</script></body></html>'''


def handle_report_get(handler) -> bool:
    path = urlparse(handler.path).path
    if path and path != "/" and not path.startswith("/api/") and path != "/report-launch":
        token = quote(path.strip("/"), safe="")
        if "/" not in token and len(token) >= 40:
            _html(handler, 200, monthly_report_html(token))
            return True
    if path == "/report-launch":
        _html(handler, 400, "<h2>این مسیر دیگر استفاده نمی‌شود.</h2><p>گزارش ماهانه از لینک اختصاصی باز می‌شود.</p>")
        return True
    return False


def handle_report_api(handler) -> bool:
    path = urlparse(handler.path).path
    if path == "/api/report-token" and handler.command == "GET":
        query = parse_qs(urlparse(handler.path).query)
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
        token = create_report_token(bot_key, str(user.id), report_type)
        _json(handler, 200, {"url": build_report_url(WEBAPP_BASE_URL, token), "expires_in_days": 30})
        return True

    prefix = "/api/public-reports/monthly/"
    if path.startswith(prefix) and handler.command == "GET":
        token = path[len(prefix):].strip("/")
        section = (parse_qs(urlparse(handler.path).query).get("section") or ["summary"])[0]
        allowed = {"summary", "tasks", "deadlines", "categories", "status", "priority"}
        if section not in allowed or not token or "/" in token:
            _json(handler, 404, {"error": "report_not_found"})
            return True
        try:
            data = monthly_report(token, section=section)
        except Exception:
            _json(handler, 500, {"error": "report_generation_failed"})
            return True
        _json(handler, 200, data) if data is not None else _json(handler, 404, {"error": "report_not_found"})
        return True
    return False


def add_monthly_web_button(markup: InlineKeyboardMarkup, user_id=None) -> InlineKeyboardMarkup:
    """Add a normal HTTP URL button. It is intentionally NOT a Telegram Web App button."""
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
