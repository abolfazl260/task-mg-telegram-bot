"""
Predefined multi-day / multi-month task templates.
Each template is a list of steps with relative day offset from today.
"""

from datetime import date, timedelta

# Template definition format:
# {
#   "id": unique key,
#   "title": display name,
#   "description": short description,
#   "category": default category,
#   "tags": default tags,
#   "priority": default priority,
#   "steps": [
#       {"title": "...", "day_offset": 0, "priority": optional override},
#       ...
#   ]
# }

TEMPLATES = [
    {
        "id": "lang_en_3m",
        "title": "آموزش زبان انگلیسی (۳ ماهه)",
        "description": "برنامه ۳ ماهه یادگیری زبان انگلیسی — واژگان، گرامر، مکالمه و آزمون",
        "category": "آموزش زبان",
        "tags": "زبان انگلیسی",
        "priority": "medium",
        "steps": [
            # ماه ۱ — پایه
            {"title": "تعیین سطح فعلی زبان انگلیسی", "day_offset": 0, "priority": "high"},
            {"title": "نصب و راه‌اندازی اپلیکیشن یادگیری (Duolingo / Anki)", "day_offset": 0},
            {"title": "یادگیری ۵۰ واژه پرکاربرد پایه — هفته ۱", "day_offset": 1},
            {"title": "تمرین گرامر: زمان حال ساده", "day_offset": 3},
            {"title": "یادگیری ۵۰ واژه جدید — هفته ۲", "day_offset": 8},
            {"title": "تمرین مکالمه ساده روزمره (۵ دقیقه)", "day_offset": 10},
            {"title": "یادگیری ۵۰ واژه — هفته ۳", "day_offset": 15},
            {"title": "تمرین گرامر: زمان گذشته ساده", "day_offset": 17},
            {"title": "یادگیری ۵۰ واژه — هفته ۴", "day_offset": 22},
            {"title": "مرور ماه اول + آزمون کوتاه", "day_offset": 28, "priority": "high"},
            # ماه ۲ — متوسط
            {"title": "شروع گوش دادن به پادکست ساده انگلیسی", "day_offset": 30},
            {"title": "یادگیری ۷۰ واژه سطح متوسط — هفته ۵", "day_offset": 32},
            {"title": "تمرین گرامر: حال استمراری و آینده", "day_offset": 35},
            {"title": "نوشتن یک پاراگراف روزانه (۳ روز)", "day_offset": 38},
            {"title": "یادگیری ۷۰ واژه — هفته ۶", "day_offset": 42},
            {"title": "تماشای یک ویدیوی کوتاه انگلیسی با زیرنویس", "day_offset": 45},
            {"title": "تمرین مکالمه ۱۵ دقیقه‌ای", "day_offset": 48},
            {"title": "یادگیری ۷۰ واژه — هفته ۷", "day_offset": 52},
            {"title": "تمرین گرامر: شرطی نوع اول", "day_offset": 55},
            {"title": "مرور ماه دوم + آزمون", "day_offset": 58, "priority": "high"},
            # ماه ۳ — پیشرفته‌تر
            {"title": "شروع کتاب داستان کوتاه انگلیسی", "day_offset": 60},
            {"title": "یادگیری ۱۰۰ واژه تخصصی علاقه‌مندی", "day_offset": 63},
            {"title": "تمرین لیسنینگ بدون زیرنویس", "day_offset": 68},
            {"title": "نوشتن ایمیل رسمی به انگلیسی", "day_offset": 72},
            {"title": "مکالمه آزاد ۲۰ دقیقه‌ای", "day_offset": 78},
            {"title": "آزمون تعیین سطح نهایی", "day_offset": 85, "priority": "high"},
            {"title": "برنامه‌ریزی ادامه یادگیری بعد از ۳ ماه", "day_offset": 90},
        ],
    },
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
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def list_templates():
    return TEMPLATES


def expand_template(template: dict, start: date | None = None):
    """
    Expand a template into concrete task dicts ready for create_task.
    Returns list of {title, priority, deadline, category, tags}
    """
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
        })

    return result
