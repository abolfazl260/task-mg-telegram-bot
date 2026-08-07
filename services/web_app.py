from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import WEB_APP_API_BASE_URL, WEB_APP_URL


def get_web_app_url():
    """Return the Mini App URL, optionally including the backend API URL.

    WEB_APP_URL is the public frontend URL opened by Telegram.
    WEB_APP_API_BASE_URL is optional and can point the frontend to a separate core/API.
    """

    if not WEB_APP_API_BASE_URL:
        return WEB_APP_URL

    parts = urlsplit(WEB_APP_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["api_base_url"] = WEB_APP_API_BASE_URL
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query),
        parts.fragment,
    ))
