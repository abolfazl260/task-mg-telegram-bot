from services.calendar_pdf_service import _task_map


def test_task_map_excludes_completed_and_cancelled_tasks():
    tasks = [
        {"title": "فعال", "deadline": "2026-08-12", "status": "pending"},
        {"title": "در حال انجام", "deadline": "2026-08-13", "status": "in_progress"},
        {"title": "انجام شده", "deadline": "2026-08-14", "status": "done"},
        {"title": "لغو شده", "deadline": "2026-08-15", "status": "cancelled"},
    ]
    result = _task_map(tasks, 1405, 5)
    assert result[21] == ["فعال"]
    assert result[22] == ["در حال انجام"]
    assert 23 not in result
    assert 24 not in result
