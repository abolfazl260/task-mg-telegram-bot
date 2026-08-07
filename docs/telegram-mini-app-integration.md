# اتصال Telegram Mini App به وب‌سایت و Core جداگانه

در Telegram Mini App سه بخش جدا دارید:

1. **Bot**: همین پروژه پایتونی که فقط دکمه وب اپ را به تلگرام می‌دهد.
2. **Web App / Frontend**: صفحه‌ای که کاربر داخل تلگرام باز می‌کند؛ مثلا `https://machino24.ir/telegram-mini-app-tasksmg/`.
3. **Core / Backend API**: سرویس اصلی شما که داده‌ها را می‌خواند و می‌نویسد؛ می‌تواند روی دامنه، ساب‌دامین یا سرور دیگری باشد.

بنابراین اگر Core جای دیگری است، لازم نیست آدرس Core همان آدرس Web App باشد. Bot فقط آدرس Frontend را باز می‌کند و Frontend باید با API جداگانه شما صحبت کند.

## تنظیمات لازم در ربات

در فایل `.env` ربات این متغیرها را تنظیم کنید:

```env
BOT_TOKEN=123456:ABC-DEF...
WEB_APP_URL=https://machino24.ir/telegram-mini-app-tasksmg/
WEB_APP_API_BASE_URL=https://api.example.com
```

- `WEB_APP_URL`: آدرس صفحه وب/فرانت‌اندی که در تلگرام باز می‌شود.
- `WEB_APP_API_BASE_URL`: آدرس Core یا API جداگانه شما. این مقدار اختیاری است؛ اگر تنظیم شود، ربات آن را به صورت query string با نام `api_base_url` به آدرس وب اپ اضافه می‌کند.

مثال آدرسی که در تلگرام باز می‌شود:

```text
https://machino24.ir/telegram-mini-app-tasksmg/?api_base_url=https%3A%2F%2Fapi.example.com
```

## چیزی که باید در خود وب‌سایت اضافه کنید

در صفحه وب اپ باید اسکریپت رسمی Telegram Web Apps را اضافه کنید و داده ورود کاربر را از `window.Telegram.WebApp.initData` بگیرید. سپس هر درخواست به Core را همراه همین `initData` بفرستید تا Backend بتواند مطمئن شود درخواست واقعا از تلگرام آمده است.

نمونه ساده Frontend:

```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
  const tg = window.Telegram.WebApp;
  tg.ready();
  tg.expand();

  const params = new URLSearchParams(window.location.search);
  const apiBaseUrl = params.get('api_base_url') || 'https://api.example.com';
  const initData = tg.initData;
  const user = tg.initDataUnsafe?.user;

  async function loadTasks() {
    const response = await fetch(`${apiBaseUrl}/api/tasks`, {
      headers: {
        Authorization: `tma ${initData}`,
      },
    });

    if (!response.ok) {
      throw new Error('Cannot load tasks');
    }

    return response.json();
  }
</script>
```

## چیزی که باید در Core / Backend اضافه کنید

Backend باید هر درخواست Mini App را با `initData` تلگرام اعتبارسنجی کند. این اعتبارسنجی باید سمت سرور انجام شود، نه فقط در JavaScript، چون داده‌های مرورگر قابل جعل هستند.

منطق کلی Backend:

1. مقدار `Authorization` را بخوانید.
2. اگر با `tma ` شروع می‌شود، ادامه آن همان `initData` است.
3. `initData` را با `BOT_TOKEN` اعتبارسنجی کنید.
4. از فیلد `user.id` تلگرام به عنوان شناسه کاربر استفاده کنید.
5. داده‌های همان کاربر را برگردانید یا تغییر دهید.

نمونه مسیرهای پیشنهادی API:

```text
GET    /api/tasks
POST   /api/tasks
PATCH  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
GET    /api/reports/summary
```

## CORS بین وب اپ و Core

اگر وب اپ روی `machino24.ir` است ولی Core روی دامنه دیگری است، روی Core باید CORS را برای دامنه وب اپ فعال کنید:

```text
Access-Control-Allow-Origin: https://machino24.ir
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Allow-Methods: GET, POST, PATCH, DELETE, OPTIONS
```

## نکته مهم امنیتی

`initDataUnsafe` فقط برای نمایش سریع اطلاعات در Frontend مناسب است. برای مجوز دسترسی به داده‌ها، همیشه `initData` خام را به Backend بفرستید و در Backend آن را با `BOT_TOKEN` بررسی کنید.
