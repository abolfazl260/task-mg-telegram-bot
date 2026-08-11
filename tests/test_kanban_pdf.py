from services.kanban_pdf_service import active_statuses, build_kanban_pdf, _short_title


def test_active_statuses_are_dynamic_and_exclude_terminal_states():
    tasks = [
        {"status": "pending", "title": "A"},
        {"status": "custom_review", "title": "B"},
        {"status": "done", "title": "C"},
        {"status": "cancelled", "title": "D"},
        {"status": "preparation", "title": "E"},
    ]
    assert active_statuses(tasks) == ["pending", "custom_review"]


def test_title_limit_is_single_line():
    title = "این عنوان بسیار طولانی است و باید برای باکس کانبان کوتاه شود"
    short = _short_title(title)
    assert len(short) <= 52
    assert "\n" not in short


def test_pdf_is_generated():
    pdf = build_kanban_pdf([
        {"id": "1", "title": "کار اول", "status": "pending", "priority": "high"},
        {"id": "2", "title": "کار دوم", "status": "in_progress", "priority": "medium"},
        {"id": "3", "title": "کار انجام‌شده", "status": "done", "priority": "low"},
    ])
    data = pdf.getvalue()
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
