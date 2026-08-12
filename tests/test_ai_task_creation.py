import unittest
from unittest.mock import patch

from services.groq_service import parse_task_request


class AITaskParsingTests(unittest.TestCase):
    @patch("services.groq_service._groq_request")
    def test_create_task_draft(self, groq_request):
        groq_request.return_value = '{"action":"CREATE_TASK","title":"جلسه با شرکت مدیران خودرو","deadline":"2026-08-12 14:00","priority":"medium","category":"","tags":"","description":"جلسه ساعت ۲ امروز"}'
        result = parse_task_request(123, "برای امروز جلسه ساعت ۲ دارم با شرکت مدیران خودرو")
        self.assertEqual(result["action"], "CREATE_TASK")
        self.assertEqual(result["title"], "جلسه با شرکت مدیران خودرو")
        self.assertEqual(result["deadline"], "2026-08-12 14:00")
        self.assertEqual(result["priority"], "medium")

    @patch("services.groq_service._groq_request")
    def test_chat_request_is_not_created(self, groq_request):
        groq_request.return_value = '{"action":"CHAT"}'
        result = parse_task_request(123, "امروز روی چه کاری تمرکز کنم؟")
        self.assertEqual(result, {"action": "CHAT"})

    @patch("services.groq_service._groq_request")
    def test_invalid_deadline_is_removed(self, groq_request):
        groq_request.return_value = '{"action":"CREATE_TASK","title":"تماس با مشتری","deadline":"امروز ساعت ۲","priority":"high"}'
        result = parse_task_request(123, "امروز ساعت ۲ با مشتری تماس بگیر")
        self.assertEqual(result["deadline"], "")
        self.assertEqual(result["priority"], "high")


if __name__ == "__main__":
    unittest.main()
