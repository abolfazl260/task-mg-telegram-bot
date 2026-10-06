from urllib.parse import urlparse

from webapp.report_routes import report_token_from_path
from webapp.report_tokens import build_report_url


def test_generated_report_url_round_trips_to_original_token():
    token = "yPZXCdx46JlTqY60ZNINajcv4PHpo1jBc7lfUv9KclU"
    url = build_report_url("http://172.245.5.27:8081", token)

    assert url == f"http://172.245.5.27:8081/report/{token}"
    assert report_token_from_path(urlparse(url).path) == token


def test_legacy_direct_token_path_remains_supported():
    token = "a" * 43

    assert report_token_from_path(f"/{token}") == token


def test_non_report_nested_paths_are_not_treated_as_report_tokens():
    token = "a" * 43

    assert report_token_from_path(f"/tasks/{token}") is None
    assert report_token_from_path("/report/short") is None
