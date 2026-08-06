from telegram import Update
from telegram.ext import ContextTypes

from handlers.menu import main_menu


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    text = f"""
# 👋 سلام {user.first_name}


## 📋 Task Manager Bot


دستیار هوشمند مدیریت کارها، جلسات و اقدامات شما آماده است.


🚀 امکانات فعلی:


✅ ایجاد و مدیریت تسک

📅 تعیین زمان انجام

🎯 اولویت‌بندی کارها

📋 مشاهده لیست تسک‌های فعال

⏳ محاسبه زمان باقی‌مانده

📊 داشبورد وضعیت کارها


---

## 🎯 اولویت‌ها


🔴 بالا
کارهای مهم و فوری


🟠 متوسط
کارهای روزمره


🟢 پایین
کارهای قابل برنامه‌ریزی


---

## 📌 وضعیت‌ها


⏳ در انتظار

🚀 در حال انجام

✅ انجام شده


---

برای شروع یکی از گزینه‌های زیر را انتخاب کنید 👇
"""


    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message":{
                "markdown": text
            }
        }
    )


    await update.message.reply_text(
        "منوی اصلی:",
        reply_markup=main_menu()
    )