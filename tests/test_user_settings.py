import pytest

from services import user_service


@pytest.mark.asyncio
async def test_date_format_switching_and_timezone_updates(test_db):
    assert await user_service.set_user_date_format_async("123", "gregorian")
    assert await user_service.get_user_date_format_async("123") == "gregorian"

    assert await user_service.set_user_date_format_async("123", "jalali")
    assert await user_service.get_user_date_format_async("123") == "jalali"

    assert await user_service.set_user_timezone_async("123", "Asia/Tehran")
    assert await user_service.get_user_timezone_async("123") == "Asia/Tehran"

    assert not await user_service.set_user_timezone_async("123", "Not/A/Timezone")
    assert await user_service.get_user_timezone_async("123") == "Asia/Tehran"


@pytest.mark.asyncio
async def test_invalid_date_format_is_rejected(test_db):
    assert not await user_service.set_user_date_format_async("123", "lunar")
