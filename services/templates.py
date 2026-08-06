"""
Predefined multi-day / multi-month task templates.
Each template is a list of steps with relative day offset from today.
"""

from datetime import date, timedelta


def _a1_a2_intensive(lang_fa: str, lang_tag: str, resources: dict):
    """Build a comprehensive 60-day A1→A2 intensive plan for one language."""

    app = resources["app"]
    course = resources["course"]
    podcast = resources["podcast"]
    yt = resources["youtube"]
    book = resources["book"]

    steps = [
        {"title": f"تعیین سطح فعلی {lang_fa} (آزمون آنلاین A1)", "day_offset": 0, "priority": "high",
         "description": "یک آزمون تعیین سطح رایگان بزن و نمره را یادداشت کن."},
        {"title": f"نصب ابزارها: {app} + Anki + دیکشنری", "day_offset": 0,
         "description": f"اپ {app}، Anki (فلش‌کارت) و یک دیکشنری خوب نصب شود."},
        {"title": f"آشنایی با الفبا و تلفظ پایه {lang_fa}", "day_offset": 1,
         "description": "صداهای خاص زبان را با تکرار و گوش دادن تمرین کن."},
        {"title": "یادگیری ۵۰ واژه ضروری روزمره (سلام، اعداد، رنگ‌ها)", "day_offset": 2,
         "description": "واژه‌ها را در Anki اضافه کن و هر روز مرور کن."},
        {"title": "گرامر: ضمایر شخصی + فعل «بودن»", "day_offset": 3,
         "description": f"از منبع {course} بخش مربوطه را بخوان و ۱۰ جمله بساز."},
        {"title": "مکالمه: معرفی خود (نام، سن، ملیت، شغل)", "day_offset": 4,
         "description": "متن معرفی را بنویس، بلند بخوان و ضبط کن."},
        {"title": "۵۰ واژه جدید: خانواده، خانه، غذا", "day_offset": 5},
        {"title": "گرامر: زمان حال ساده افعال پرکاربرد", "day_offset": 6},
        {"title": "تمرین لیسنینگ ۵–۱۰ دقیقه (سطح A1)", "day_offset": 7,
         "description": f"از {podcast} یا {yt} محتوای سطح مبتدی گوش بده."},
        {"title": "۵۰ واژه: خرید، لباس، قیمت‌ها", "day_offset": 9},
        {"title": "گرامر: سوال ساختن (کجا، کی، چه، چرا)", "day_offset": 10},
        {"title": "نقش‌آفرینی: خرید از فروشگاه", "day_offset": 11,
         "description": "دیالوگ کوتاه بنویس و با صدای بلند تمرین کن."},
        {"title": "۵۰ واژه: جهت‌ها، شهر، وسایل نقلیه", "day_offset": 12},
        {"title": "گرامر: حروف اضافه مکان و زمان", "day_offset": 13},
        {"title": "نوشتن: توصیف محل زندگی (۸–۱۰ جمله)", "day_offset": 14, "priority": "high"},
        {"title": "۵۰ واژه: شغل، تحصیل، برنامه‌های روزانه", "day_offset": 16},
        {"title": "گرامر: افعال کمکی و منفی کردن جمله", "day_offset": 17},
        {"title": "لیسنینگ + تکرار سایه (shadowing) ۱۰ دقیقه", "day_offset": 18,
         "description": f"با {yt} یک ویدیوی کوتاه را جمله به جمله تکرار کن."},
        {"title": "۵۰ واژه: آب‌وهوا، فصل‌ها، فعالیت‌های اوقات فراغت", "day_offset": 19},
        {"title": "گرامر: زمان حال استمراری / ساختار در حال انجام", "day_offset": 20},
        {"title": "آزمون میان‌دوره A1 + مرور نقاط ضعف", "day_offset": 21, "priority": "high",
         "description": "آزمون کوتاه بزن و واژه‌ها/گرامرهای غلط را لیست کن."},
        {"title": "مرور ۲۰۰ واژه اول با Anki (روزانه)", "day_offset": 23},
        {"title": "مکالمه: یک روز معمولی خود را تعریف کن", "day_offset": 24,
         "description": "۲–۳ دقیقه صحبت ضبط‌شده؛ بدون نگاه به متن."},
        {"title": "خواندن متن کوتاه A1 + خلاصه‌نویسی", "day_offset": 25,
         "description": f"از کتاب {book} یک متن کوتاه بخوان."},
        {"title": "گرامر: صفت‌ها و ترتیب آن‌ها", "day_offset": 26},
        {"title": "تمرین نوشتاری: ایمیل کوتاه دوستانه", "day_offset": 27},
        {"title": "جمع‌بندی ماه اول + چک‌لیست مهارت‌های A1", "day_offset": 28, "priority": "high",
         "description": "لیست مهارت‌های A1 را تیک بزن؛ هر جا ضعف داری علامت بگذار."},
        {"title": "۶۰ واژه سطح A2: سفر، هتل، رزرو", "day_offset": 30},
        {"title": "گرامر: زمان گذشته ساده", "day_offset": 31,
         "description": "افعال بی‌قاعده پرکاربرد را جدا حفظ کن."},
        {"title": "نقش‌آفرینی: رزرو هتل / خرید بلیت", "day_offset": 32},
        {"title": "۶۰ واژه: احساسات، سلامتی، پزشک", "day_offset": 33},
        {"title": "گرامر: گذشته استمراری / ساختارهای گذشته مکمل", "day_offset": 34},
        {"title": "لیسنینگ ۱۵ دقیقه‌ای سطح A2", "day_offset": 35,
         "description": f"از {podcast} قسمت مناسب A2 گوش بده و ۵ واژه جدید یادداشت کن."},
        {"title": "۶۰ واژه: کار، مصاحبه، محل کار", "day_offset": 37},
        {"title": "گرامر: آینده (will / going to یا معادل)", "day_offset": 38},
        {"title": "نوشتن: برنامه‌های آینده شغلی/تحصیلی (۱۲–۱۵ جمله)", "day_offset": 39, "priority": "high"},
        {"title": "۶۰ واژه: فناوری، اینترنت، شبکه‌های اجتماعی", "day_offset": 40},
        {"title": "گرامر: جملات شرطی نوع صفر و یک", "day_offset": 41},
        {"title": "مکالمه آزاد ۵ دقیقه‌ای درباره علایق", "day_offset": 42,
         "description": "بدون متن از قبل؛ فقط نکات کلیدی روی کاغذ."},
        {"title": "۶۰ واژه: محیط زیست، شهر، مشکلات شهری", "day_offset": 44},
        {"title": "گرامر: مجهول ساده (passive) در حد A2", "day_offset": 45},
        {"title": f"خواندن داستان کوتاه ساده ({book})", "day_offset": 46,
         "description": "یک فصل/بخش کوتاه؛ واژه‌های جدید را در Anki بگذار."},
        {"title": "تمرین درک مطلب + پاسخ به سوالات متن", "day_offset": 47},
        {"title": "گرامر: نقل‌قول غیرمستقیم ساده", "day_offset": 48},
        {"title": "آزمون آزمایشی A2 (نمونه سوال)", "day_offset": 49, "priority": "high",
         "description": "Listening + Reading + Writing کوتاه؛ نقاط ضعف را لیست کن."},
        {"title": "مرور فشرده همه گرامرهای A1–A2", "day_offset": 51,
         "description": "یک صفحه خلاصه گرامر برای خودت بنویس."},
        {"title": "مرور Anki: حداقل ۳۰۰ کارت فعال", "day_offset": 52},
        {"title": "مکالمه ۱۰ دقیقه‌ای شبیه‌سازی مصاحبه/سفر", "day_offset": 53, "priority": "high"},
        {"title": "نوشتن نهایی: متن ۱۵۰ کلمه‌ای درباره تجربه یادگیری", "day_offset": 54},
        {"title": "لیسنینگ نهایی بدون زیرنویس (۱۰–۱۵ دقیقه)", "day_offset": 55},
        {"title": "آزمون تعیین سطح نهایی (هدف: A2)", "day_offset": 57, "priority": "high",
         "description": "همان نوع آزمون اول را تکرار کن و پیشرفت را مقایسه کن."},
        {"title": "برنامه‌ریزی مسیر بعد از A2 (منابع B1)", "day_offset": 59,
         "description": "۳ منبع برای سطح بعدی انتخاب و در تقویم بگذار."},
    ]

    return {
        "id": f"lang_{lang_tag}_a1a2_60d",
        "title": f"{lang_fa} فشرده A1→A2 (۲ ماهه)",
        "description": (
            f"برنامه جامع و فشرده ۶۰ روزه برای رسیدن از A1 به A2 در زبان {lang_fa}. "
            "شامل واژگان، گرامر، لیسنینگ، مکالمه، خواندن و نوشتن."
        ),
        "category": "آموزش زبان",
        "tags": f"{lang_fa} A1 A2 فشرده",
        "priority": "high",
        "steps": steps,
    }


TEMPLATES = [
    _a1_a2_intensive(
        lang_fa="انگلیسی",
        lang_tag="en",
        resources={
            "app": "Duolingo / Elsa Speak",
            "course": "English Grammar in Use (Elementary)",
            "podcast": "BBC Learning English — The English We Speak",
            "youtube": "English with Lucy / Easy English",
            "book": "Oxford Bookworms Starter/Stage 1",
        },
    ),
    _a1_a2_intensive(
        lang_fa="آلمانی",
        lang_tag="de",
        resources={
            "app": "Duolingo / Babbel Deutsch",
            "course": "Menschen A1–A2 / Grammatik aktiv",
            "podcast": "Slow German / Deutsch – warum nicht?",
            "youtube": "Deutsch für Euch / Easy German",
            "book": "Cafe in Berlin (A1–A2) یا خواندنی‌های ساده Hueber",
        },
    ),
    _a1_a2_intensive(
        lang_fa="فرانسوی",
        lang_tag="fr",
        resources={
            "app": "Duolingo / Busuu Français",
            "course": "Grammaire Progressive du Français (Débutant)",
            "podcast": "Coffee Break French / InnerFrench (شروع آرام)",
            "youtube": "Learn French with Alexa / Français Authentique",
            "book": "LFF A1 / short graded readers",
        },
    ),
    {
        "id": "fitness_30d",
        "title": "برنامه تناسب اندام ۳۰ روزه",
        "description": "۳۰ روز ورزش منظم — ترکیبی از کاردیو و قدرتی",
        "category": "سلامت",
        "tags": "ورزش تناسب‌اندام",
        "priority": "medium",
        "steps": [
            {"title": "اندازه‌گیری وزن و ثبت وضعیت فعلی", "day_offset": 0, "priority": "high"},
            {"title": "خرید / آماده‌سازی وسایل ورزشی ساده", "day_offset": 0},
            {"title": "روز ۱–۳: پیاده‌روی ۲۰ دقیقه‌ای", "day_offset": 1},
            {"title": "روز ۴–۷: تمرینات بدنسازی سبک در خانه", "day_offset": 4},
            {"title": "هفته ۲: افزایش زمان کاردیو به ۳۰ دقیقه", "day_offset": 8},
            {"title": "هفته ۲: تمرین قدرتی ۲ جلسه", "day_offset": 10},
            {"title": "هفته ۳: ترکیب کاردیو + قدرتی", "day_offset": 15},
            {"title": "هفته ۳: یک روز استراحت فعال (یوگا/کشش)", "day_offset": 18},
            {"title": "هفته ۴: چالش نهایی ۳۰ دقیقه ورزش روزانه", "day_offset": 22},
            {"title": "روز ۳۰: اندازه‌گیری مجدد و مقایسه", "day_offset": 29, "priority": "high"},
        ],
    },
    {
        "id": "project_launch_6w",
        "title": "راه‌اندازی پروژه (۶ هفته)",
        "description": "از ایده تا لانچ — برنامه ۶ هفته‌ای برای یک پروژه کوچک",
        "category": "پروژه",
        "tags": "راه‌اندازی لانچ",
        "priority": "high",
        "steps": [
            {"title": "تعریف دقیق ایده و هدف پروژه", "day_offset": 0, "priority": "high"},
            {"title": "تحقیق بازار و رقبا", "day_offset": 2},
            {"title": "نوشتن لیست ویژگی‌های MVP", "day_offset": 5},
            {"title": "طراحی وایرفریم / اسکچ اولیه", "day_offset": 7},
            {"title": "شروع پیاده‌سازی هسته اصلی", "day_offset": 10},
            {"title": "تکمیل MVP و تست داخلی", "day_offset": 21},
            {"title": "جمع‌آوری بازخورد از ۳ نفر", "day_offset": 28},
            {"title": "رفع باگ‌ها و بهبود بر اساس بازخورد", "day_offset": 32},
            {"title": "آماده‌سازی صفحه معرفی / لندینگ", "day_offset": 35},
            {"title": "لانچ رسمی و انتشار", "day_offset": 40, "priority": "high"},
            {"title": "پیگیری بازخورد هفته اول بعد از لانچ", "day_offset": 47},
        ],
    },
    {
        "id": "reading_habit_30d",
        "title": "عادت کتابخوانی ۳۰ روزه",
        "description": "ساخت عادت مطالعه روزانه به مدت یک ماه",
        "category": "توسعه فردی",
        "tags": "کتاب مطالعه",
        "priority": "low",
        "steps": [
            {"title": "انتخاب کتاب اول", "day_offset": 0, "priority": "high"},
            {"title": "مطالعه ۲۰ صفحه — روزهای ۱ تا ۷", "day_offset": 1},
            {"title": "یادداشت ۳ نکته کلیدی هفته اول", "day_offset": 7},
            {"title": "مطالعه ۳۰ صفحه — هفته ۲", "day_offset": 8},
            {"title": "یادداشت خلاصه فصل‌های خوانده‌شده", "day_offset": 14},
            {"title": "ادامه مطالعه — هفته ۳", "day_offset": 15},
            {"title": "اشتراک‌گذاری یک نکته با یک دوست", "day_offset": 21},
            {"title": "پایان کتاب و انتخاب کتاب بعدی", "day_offset": 28, "priority": "high"},
            {"title": "بررسی عادت مطالعه و برنامه‌ریزی ماه بعد", "day_offset": 29},
        ],
    },
]


def get_template(template_id: str):
    for t in list_templates():
        if t["id"] == template_id:
            return t
    return None


def list_templates():
    from services.extra_templates import EXTRA_TEMPLATES
    return TEMPLATES + EXTRA_TEMPLATES


def expand_template(template: dict, start: date | None = None):
    if start is None:
        start = date.today()

    result = []
    default_priority = template.get("priority", "medium")
    category = template.get("category", "")
    tags = template.get("tags", "")

    for step in template["steps"]:
        deadline = (start + timedelta(days=step["day_offset"])).isoformat()
        result.append({
            "title": step["title"],
            "priority": step.get("priority", default_priority),
            "deadline": deadline,
            "category": category,
            "tags": tags,
            "description": step.get("description", ""),
        })

    return result
