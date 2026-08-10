from handlers import guest


def test_guest_text_extractor_title_priority_and_deadline():
    raw = "@TaskBot add Prepare report 2026-08-20 فوری"
    assert guest._extract_title(raw, "TaskBot") == "Prepare report 2026-08-20 فوری"
    assert guest._extract_priority(raw) == "high"
    assert guest._extract_deadline(raw) == "2026-08-20"


def test_guest_extractor_supports_jalali_deadline():
    raw = "ثبت کار جلسه 1405-05-29 مهم"
    assert guest._extract_priority(raw) == "high"
    assert guest._extract_deadline(raw)


def test_guest_defaults_to_medium_priority_and_strips_command():
    assert guest._extract_title("/todo Buy milk", "") == "Buy milk"
    assert guest._extract_priority("Buy milk") == "medium"
    assert guest._extract_deadline("Buy milk tomorrow") == ""
