from webapp.report_tokens import _hash, build_report_url


def test_report_token_is_not_based_on_user_id():
    token_a = __import__("secrets").token_urlsafe(32)
    token_b = __import__("secrets").token_urlsafe(32)
    assert token_a != token_b
    assert str(123456789) not in token_a
    assert _hash(token_a) != _hash(token_b)


def test_report_url_contains_only_opaque_token():
    url = build_report_url("https://reports.example.com", "A" * 43)
    assert url == "https://reports.example.com/report/" + "A" * 43
    assert "user_id" not in url
    assert "123" not in url
