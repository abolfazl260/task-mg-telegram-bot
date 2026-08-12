import unittest
from unittest.mock import patch

from services.task_intelligence import normalize_user_text, parse_task_request_smart


class SmartTaskIntelligenceTests(unittest.TestCase):
    def test_normalizes_persian_digits_and_unicode(self):
        self.assertEqual(normalize_user_text("كارت ۱۲۳  يک کار"), "کارت 123 یک کار")

    @patch("services.task_intelligence.parse_task_request")
    def test_voice_style_text_keeps_task_date_and_time(self, parser):
        parser.return_value = {
            "action": "CREATE_TASK",
            "title": "جلسه با تیم فروش",
            "deadline": "",
            "priority": "low",
            "category": "کاری/شغلی",
            "tags": "#جلسه",
            "description": "",
            "repeat_type": "",
            "target": "",
            "reminder_time": "",
        }
        result = parse_task_request_smart(123, "فردا ساعت ۹ جلسه با تیم فروش دارم")
        self.assertEqual(result["action"], "CREATE_TASK")
        self.assertRegex(result["deadline"], r"^\d{4}-\d{2}-\d{2} 09:00$")

    @patch("services.task_intelligence.parse_task_request")
    def test_weekly_count_is_not_mistaken_for_time(self, parser):
        parser.return_value = {
            "action": "CREATE_HABIT",
            "title": "ورزش",
            "deadline": "",
            "priority": "low",
            "category": "سلامت",
            "tags": "#ورزش",
            "description": "",
            "repeat_type": "weekly",
            "target": "۳ بار در هفته",
            "reminder_time": "",
        }
        result = parse_task_request_smart(123, "هر هفته 3 بار ورزش کنم")
        self.assertEqual(result["action"], "CREATE_HABIT")
        self.assertEqual(result["repeat_type"], "weekly")
        self.assertEqual(result["reminder_time"], "")

    @patch("services.task_intelligence.parse_task_request")
    def test_explicit_urgent_priority_wins(self, parser):
        parser.return_value = {
            "action": "CREATE_TASK", "title": "پرداخت قبض", "deadline": "",
            "priority": "low", "category": "مالی", "tags": "#مالی", "description": "",
            "repeat_type": "", "target": "", "reminder_time": "",
        }
        result = parse_task_request_smart(123, "پرداخت قبض خیلی مهم و فوری")
        self.assertEqual(result["priority"], "high")

    @patch("services.task_intelligence.parse_task_request")
    def test_action_sentence_is_not_left_as_chat(self, parser):
        parser.return_value = {"action": "CHAT"}
        result = parse_task_request_smart(123, "فردا گزارش را برای مدیرم ارسال کن")
        self.assertEqual(result["action"], "CREATE_TASK")


if __name__ == "__main__":
    unittest.main()
