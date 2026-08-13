# استقرار Telegram Web App

## معماری پیشنهادی

در production، پورت داخلی Web App را مستقیماً عمومی نکنید:

```text
Internet / Telegram
        |
      HTTPS :443
        |
      Nginx
        |
  127.0.0.1:8081
        |
 Telegram Web App server
```

## متغیرهای محیطی

در فایل `.env` سرور:

```env
WEBAPP_HOST=127.0.0.1
WEBAPP_PORT=8081
WEBAPP_BASE_URL=https://web.example.com
WEBAPP_BOT_TOKEN=<telegram-bot-token>
```

`WEBAPP_BASE_URL` باید URL عمومی و HTTPS وب‌اپ باشد و بدون `/` انتهایی تنظیم شود.

`WEBAPP_PORT` فقط پورت داخلی برنامه است و نیازی نیست در فایروال عمومی باز شود.

## Nginx

نمونه کانفیگ:

```nginx
server {
    listen 443 ssl http2;
    server_name web.example.com;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

گواهی TLS باید برای همان دامنه فعال باشد. Telegram Web App را با HTTP عمومی اجرا نکنید.

## بررسی سلامت

بعد از اجرای سرویس:

```bash
curl http://127.0.0.1:8081/health
curl https://web.example.com/health
```

هر دو باید پاسخ JSON سلامت سرویس را برگردانند.

## اجرای سرویس

سرور Web App باید همراه با Bot اجرا شود یا توسط systemd/supervisor به‌صورت مستقل مدیریت شود. در صورت استفاده از systemd، متغیرهای `.env` باید در محیط همان سرویس نیز در دسترس باشند.

## نکته امنیتی

پورت `8081` را عمومی نکنید. فقط Nginx باید به آن دسترسی داشته باشد. احراز هویت API همچنان با `X-Telegram-Init-Data` انجام می‌شود.
