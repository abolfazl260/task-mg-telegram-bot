from handlers.import_bulk import _validate_csv_rows


def test_valid_csv_rows_are_normalized():
    data = (
        "title,priority,deadline,category,tags,description\n"
        "Write tests,high,2026-08-20,dev,pytest,unit tests\n"
    ).encode()
    rows, errors, total = _validate_csv_rows(data)
    assert total == 1
    assert errors == []
    assert rows == [{
        "title": "Write tests",
        "priority": "high",
        "deadline": "2026-08-20",
        "category": "dev",
        "tags": "pytest",
        "description": "unit tests",
    }]


def test_missing_title_is_rejected():
    data = (
        "title,priority,deadline,category,tags,description\n"
        ",medium,2026-08-20,dev,,missing title\n"
    ).encode()
    rows, errors, total = _validate_csv_rows(data)
    assert total == 1
    assert rows == []
    assert any("title" in error for error in errors)


def test_incorrect_date_format_is_rejected():
    data = (
        "title,priority,deadline,category,tags,description\n"
        "Task,high,20-08-2026,dev,,bad date\n"
    ).encode()
    rows, errors, total = _validate_csv_rows(data)
    assert total == 1
    assert rows == []
    assert any("deadline" in error for error in errors)


def test_jalali_csv_deadline_is_converted_to_gregorian():
    data = (
        "title,priority,deadline,category,tags,description\n"
        "Task,medium,1405-05-29,dev,,jalali\n"
    ).encode()
    rows, errors, _ = _validate_csv_rows(data)
    assert errors == []
    assert rows[0]["deadline"] == "2026-08-20"
