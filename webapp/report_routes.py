"""Private web-report routes and Telegram report links."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

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
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>گزارش ماهانه</title><style>body{{font-family:system-ui,-apple-system,sans-serif;background:#f5f7fb;margin:0;color:#172033}}main{{max-width:900px;margin:24px auto;padding:16px}}.card{{background:#fff;border-radius:18px;padding:20px;margin:12px 0;box-shadow:0 4px 18px #0000000d}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}.metric{{font-size:28px;font-weight:700}}.muted{{color:#687386}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #edf0f5;text-align:right}}.error{{color:#b42318}}</style></head><body><main><div id="app" class="card">در حال بارگذاری گزارش...</div></main><script>
const token={safe_token};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
async function load(){{const r=await fetch('/api/public-reports/monthly/'+encodeURIComponent(token),{{cache:'no-store'}});const d=await r.json();if(!r.ok)throw new Error('لینک گزارش معتبر نیست یا منقضی شده است.');const s=d.summary;document.getElementById('app').innerHTML=`<h1>📊 گزارش ماهانه</h1><p class="muted">${{esc(d.period.jalali)}} · ${{esc(d.period.gregorian)}}</p><div class="grid"><div class="card"><div class="metric">${{s.total}}</div><div>کل وظایف</div></div><div class="card"><div class="metric">${{s.done}}</div><div>انجام‌شده</div></div><div class="card"><div class="metric">${{s.in_progress}}</div><div>در حال انجام</div></div><div class="card"><div class="metric">${{s.completion_rate}}٪</div><div>نرخ انجام</div></div></div><div class="card"><h2>وضعیت</h2>${{d.by_status.map(x=>`<p>${{esc(x.label)}}: <b>${{x.count}}</b></p>`).join('')}}</div><div class="card"><h2>اولویت</h2>${{d.by_priority.map(x=>`<p>${{esc(x.label)}}: <b>${{x.count}}</b></p>`).join('')}}</div><div class="card"><h2>دسته‌بندی‌ها</h2>${{d.by_category.map(x=>`<p>${{esc(x.label)}}: <b>${{x.count}}</b></p>`).join('')}}</div><div class="card"><h2>جزئیات وظایف</h2><table><thead><tr><th>عنوان</th><th>وضعیت</th><th>اولویت</th><th>مهلت</th><th>دسته‌بندی</th></tr></thead><tbody>${{d.tasks.map(x=>`<tr><td>${{esc(x.title)}}</td><td>${{esc(x.status_label)}}</td><td>${{esc(x.priority_label)}}</td><td>${{esc(x.deadline||'—')}}</td><td>${{esc(x.category||'—')}}</td></tr>`).join('')}}</tbody></table></div>`}}catch(e){{document.getElementById('app').innerHTML='<h1>گزارش ماهانه</h1><p class="error">'+esc(e.message)+'</p>'}}}}load();</script></body></html>'''


def handle_report_get(handler) -> bool:
    path = urlparse(handler.path).path
    if path and path != "/" and not path.startswith("/api/") and path != "/report-launch":
        token = path.strip("/")
        if "/" not in token and len(token) >= 40:
            data = monthly_report(token)
            _html(handler, 200 if data is not None else 404, monthly_report_html(token) if data is not None else "<h2>لینک گزارش معتبر نیست یا منقضی شده است.</h2>")
            return True
    if path == "/report-launch":
        _html(handler, 400, "<h2>این مسیر دیگر استفاده نمی‌شود.</h2><p>گزارش ماهانه از لینک اختصاصی باز می‌شود.</p>")
        return True
    return False


def handle_report_api(handler) -> bool:
    path = urlparse(handler.path).path
    if path == "/api/report-token" and handler.command == "GET":
        query = parse_qs(urlparse(handler.path).query);report_type=(query.get("type") or ["monthly"])[0];bot_key=(query.get("bot_key") or [""])[0].strip()
        if report_type != "monthly" or not bot_key:_json(handler,400,{"error":"invalid_report_request"});return True
        try:user=authenticate_telegram_request(handler.headers.get("X-Telegram-Init-Data",""),bot_key)
        except Exception:_json(handler,401,{"error":"unauthorized"});return True
        token=create_report_token(bot_key,str(user.id),report_type);_json(handler,200,{"url":build_report_url(WEBAPP_BASE_URL,token),"expires_in_days":30});return True
    if path.startswith("/api/public-reports/monthly/") and handler.command == "GET":
        token=path.rsplit("/",1)[-1];data=monthly_report(token);_json(handler,200,data) if data is not None else _json(handler,404,{"error":"report_not_found"});return True
    return False


def add_monthly_web_button(markup: InlineKeyboardMarkup, user_id=None) -> InlineKeyboardMarkup:
    """Add a normal URL button. It is intentionally NOT a Telegram Web App button."""
    if user_id is None:
        user_id = viewer_id()
    if not user_id:
        return markup
    token=create_report_token(get_current_bot_key(),str(user_id),"monthly")
    url=build_report_url(WEBAPP_BASE_URL,token)
    rows=[list(row) for row in markup.inline_keyboard]
    if not any(button.text == "📊 گزارش ماهانه تحت وب" for row in rows for button in row):
        rows.insert(0,[InlineKeyboardButton("📊 گزارش ماهانه تحت وب",url=url)])
    return InlineKeyboardMarkup(rows)
