import json
from pathlib import Path


def test_habits_only_profile_contract():
    profile = json.loads((Path(__file__).parents[1] / "bots" / "habits_only.json").read_text(encoding="utf-8"))
    assert profile["features"]["tasks"] is True
    assert profile["features"]["habits"] is True
    assert profile["features"]["teams"] is True
    assert profile["features"]["templates"] is False
    assert profile["features"]["bulk_import"] is False
    assert profile["task_options"]["allow_assignment"] is False
    assert profile["task_options"]["allow_tags"] is False
    assert profile["task_options"]["allow_comments"] is True
    assert profile["task_options"]["allow_categories"] is True
    assert profile["task_options"]["allow_search"] is True
    assert profile["task_options"]["allow_ai_task_creation"] is True
