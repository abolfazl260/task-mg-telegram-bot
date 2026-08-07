# راه‌اندازی ساده Mini App وقتی Web App و Backend جدا هستند

این راهنما برای حالتی است که:

- Web App / Frontend روی آدرس عمومی مثل `https://machino24.ir/telegram-mini-app-tasksmg/` باز می‌شود.
- Backend/Core فعلا روی لپ‌تاپ شما، مثلا `http://localhost:8000`، اجرا می‌شود.
- یک سرور هم دارید که پردازش‌های پایتون را انجام می‌دهد، اما هنوز دامنه ندارد.

## اصل ماجرا

مرورگر داخل تلگرام روی گوشی یا کامپیوتر کاربر نمی‌تواند به `localhost` لپ‌تاپ شما وصل شود. `localhost` برای هر دستگاه یعنی همان دستگاه خودش، نه لپ‌تاپ شما. پس برای اینکه Web App بتواند Backend محلی شما را ببیند، باید Backend را با یک آدرس عمومی HTTPS موقت در اینترنت منتشر کنید.

مسیر درست درخواست‌ها این است:

```text
Telegram Bot -> باز کردن WEB_APP_URL
Web App -> خواندن api_base_url
Web App -> ارسال درخواست به Backend/Core
Backend/Core -> اعتبارسنجی initData تلگرام و پاسخ با داده کاربر
```

## مرحله ۱: Backend را روی لوکال اجرا کنید

مثلا اگر Backend شما با FastAPI است:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

آدرس محلی شما می‌شود:

```text
http://127.0.0.1:8000
```

## مرحله ۲: Backend لوکال را با HTTPS عمومی کنید

برای توسعه، یکی از این ابزارها را استفاده کنید:

- `ngrok`
- `cloudflared tunnel`
- `localtunnel`

مثال با ngrok:

```bash
ngrok http 8000
```

ngrok یک آدرس HTTPS می‌دهد، مثلا:

```text
https://abc-123.ngrok-free.app
```

این آدرس همان آدرس موقت Backend شماست و باید در ربات تنظیم شود.

## مرحله ۳: متغیرهای ربات را تنظیم کنید

در فایل `.env` همین پروژه:

```env
BOT_TOKEN=123456:ABC-DEF...
WEB_APP_URL=https://machino24.ir/telegram-mini-app-tasksmg/
WEB_APP_API_BASE_URL=https://abc-123.ngrok-free.app
```

بعد ربات را ری‌استارت کنید:

```bash
python main.py
```

حالا وقتی کاربر دکمه وب اپ را می‌زند، ربات این آدرس را باز می‌کند:

```text
https://machino24.ir/telegram-mini-app-tasksmg/?api_base_url=https%3A%2F%2Fabc-123.ngrok-free.app
```

## مرحله ۴: در Web App آدرس Backend را از query string بخوانید

داخل Web App باید این کار را انجام دهید:

```js
const tg = window.Telegram.WebApp;
tg.ready();

const params = new URLSearchParams(window.location.search);
const apiBaseUrl = params.get('api_base_url');
const initData = tg.initData;

const response = await fetch(`${apiBaseUrl}/api/tasks`, {
  headers: {
    Authorization: `tma ${initData}`,
  },
});
```

نکته مهم: اگر `api_base_url` خالی بود، بهتر است در Web App یک پیام خطای واضح نشان دهید، مثلا «آدرس Backend تنظیم نشده است».

## مرحله ۵: روی Backend، CORS را فعال کنید

چون Web App از دامنه `machino24.ir` باز می‌شود ولی Backend روی دامنه دیگری است، Backend باید درخواست‌های این Origin را قبول کند.

برای FastAPI:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://machino24.ir"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
```

## مرحله ۶: روی Backend، کاربر تلگرام را اعتبارسنجی کنید

Web App باید `initData` را بفرستد، اما Backend باید آن را با `BOT_TOKEN` چک کند. فقط بعد از اعتبارسنجی، از `user.id` تلگرام برای خواندن/نوشتن داده‌های همان کاربر استفاده کنید.

حداقل منطق لازم:

```text
Authorization: tma <Telegram initData>
```

Backend باید:

1. هدر `Authorization` را بخواند.
2. مقدار `initData` را از بعد از `tma ` بردارد.
3. امضای `initData` را با `BOT_TOKEN` بررسی کند.
4. `user.id` را استخراج کند.
5. فقط داده‌های همان `user.id` را برگرداند.

## اگر Backend روی سرور بدون دامنه است

برای تست سریع، ساده‌ترین کار این است که روی همان سرور هم یک Tunnel اجرا کنید:

```bash
ngrok http 8000
```

یا با Cloudflare Tunnel یک آدرس HTTPS بگیرید. سپس همان آدرس HTTPS را در `.env` ربات بگذارید:

```env
WEB_APP_API_BASE_URL=https://your-server-tunnel.example
```

اگر می‌خواهید پایدار و واقعی شود، بهتر است یکی از این دو کار را انجام دهید:

1. یک دامنه یا ساب‌دامین برای API بگیرید، مثلا `api.machino24.ir`.
2. روی سرور Nginx + HTTPS بگذارید و Backend پایتون را پشت آن اجرا کنید.

بدون دامنه هم می‌توانید با IP کار کنید، ولی برای Mini App و مرورگر بهتر است API حتما HTTPS معتبر داشته باشد. گرفتن SSL معتبر برای IP معمولا سخت‌تر از دامنه است، بنابراین دامنه یا Tunnel پایدار پیشنهاد می‌شود.

## چک‌لیست نهایی

- Backend روی لوکال یا سرور اجراست.
- Backend یک آدرس عمومی HTTPS دارد؛ مثلا ngrok یا دامنه واقعی.
- مقدار `WEB_APP_API_BASE_URL` در `.env` ربات همان آدرس HTTPS است.
- ربات ری‌استارت شده است.
- Web App مقدار `api_base_url` را می‌خواند.
- Web App در هر درخواست `Authorization: tma <initData>` می‌فرستد.
- Backend CORS را برای `https://machino24.ir` فعال کرده است.
- Backend `initData` را با `BOT_TOKEN` اعتبارسنجی می‌کند.

## اجرای API همین پروژه برای Web App

این پروژه علاوه بر ربات، یک API ساده هم دارد که Web App می‌تواند از آن داده بگیرد. برای اجرای API روی کامپیوتر خودتان:

```bash
uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

سپس آن را با ngrok عمومی کنید:

```bash
ngrok http 8000
```

و آدرس HTTPS ngrok را در `.env` ربات بگذارید:

```env
WEB_APP_API_BASE_URL=https://abc-123.ngrok-free.app
API_CORS_ORIGINS=https://machino24.ir
```

APIهای آماده:

```text
GET    /api/me
GET    /api/tasks?status=active
GET    /api/tasks?status=all
POST   /api/tasks
PATCH  /api/tasks/{task_id}/status
```

همه این APIها باید با هدر زیر صدا زده شوند:

```text
Authorization: tma <Telegram WebApp initData>
```

## کد آماده برای Frontend یا WordPress

اگر صفحه وب اپ شما روی WordPress است، می‌توانید این کد را در یک Custom HTML block یا در قالب/افزونه خود اضافه کنید. این کد لیست تسک‌های فعال کاربر تلگرام را از Backend می‌گیرد و نمایش می‌دهد:

```html
<div id="taskmg-app" dir="rtl" style="font-family: sans-serif; padding: 16px">
  <h3>تسک‌های من</h3>
  <div id="taskmg-status">در حال بارگذاری...</div>
  <ul id="taskmg-tasks"></ul>
</div>

<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
(async function () {
  const statusEl = document.getElementById('taskmg-status');
  const listEl = document.getElementById('taskmg-tasks');
  const tg = window.Telegram && window.Telegram.WebApp;

  if (!tg) {
    statusEl.textContent = 'این صفحه باید داخل Telegram باز شود.';
    return;
  }

  tg.ready();
  tg.expand();

  const params = new URLSearchParams(window.location.search);
  const apiBaseUrl = params.get('api_base_url');

  if (!apiBaseUrl) {
    statusEl.textContent = 'آدرس Backend تنظیم نشده است.';
    return;
  }

  if (!tg.initData) {
    statusEl.textContent = 'اطلاعات ورود تلگرام دریافت نشد. وب اپ را از داخل ربات باز کنید.';
    return;
  }

  try {
    const response = await fetch(`${apiBaseUrl}/api/tasks?status=active`, {
      headers: {
        Authorization: `tma ${tg.initData}`,
      },
    });

    if (!response.ok) {
      throw new Error(`خطای API: ${response.status}`);
    }

    const data = await response.json();
    const tasks = data.tasks || [];
    statusEl.textContent = tasks.length ? '' : 'تسک فعالی ندارید.';
    listEl.innerHTML = '';

    for (const task of tasks) {
      const item = document.createElement('li');
      item.textContent = `${task.title} - ${task.priority} - ${task.status}`;
      listEl.appendChild(item);
    }
  } catch (error) {
    statusEl.textContent = `خطا در دریافت داده: ${error.message}`;
  }
})();
</script>
```
