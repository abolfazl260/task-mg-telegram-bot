import secrets

from webapp.report_tokens import _hash, build_report_url


def test_report_tokens_are_opaque_and_high_entropy():
    token_a = secrets.token_urlsafe(32)
    token_b = secrets.token_urlsafe(32)
    assert len(token_a) >= 40
    assert len(token_b) >= 40
    assert token_a != token_b
    assert _hash(token_a) != _hash(token_b)


def test_report_url_does_not_expose_user_identifier():
    token = "A" * 43
    url = build_report_url("https://reports.example.com", token)
    assert url == "https://reports.example.com/report/" + token
    assert "user_id" not in url
