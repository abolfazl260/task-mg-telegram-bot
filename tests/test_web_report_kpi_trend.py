from webapp.reports import _change


def test_change_reports_percentage_and_direction_for_increase():
    assert _change(58, 51) == {
        "available": True,
        "percentage": 14,
        "direction": "up",
        "previous_total": 51,
    }


def test_change_reports_percentage_and_direction_for_decrease():
    assert _change(43, 50) == {
        "available": True,
        "percentage": 14,
        "direction": "down",
        "previous_total": 50,
    }


def test_change_handles_no_previous_data_without_inventing_percentage():
    assert _change(12, 0) == {
        "available": False,
        "percentage": None,
        "direction": "new",
        "previous_total": 0,
    }


def test_change_reports_flat_when_counts_are_equal():
    assert _change(20, 20) == {
        "available": True,
        "percentage": 0,
        "direction": "flat",
        "previous_total": 20,
    }
