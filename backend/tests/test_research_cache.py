import json

from app.services import research_cache


def test_file_research_cache_survives_a_new_store_instance(tmp_path) -> None:
    path = tmp_path / "research-last-success.json"
    first = research_cache.FileResearchCacheStore(path)

    first.put_signal(
        "000021",
        {"code": "000021", "macd_state": "DIF位于DEA上方"},
        "2026-07-21T09:42:00+08:00",
    )
    first.put_news(
        "000021",
        [{"title": "公开新闻", "url": "https://example.test/news/000021"}],
        "2026-07-21T09:43:00+08:00",
    )

    second = research_cache.FileResearchCacheStore(path)

    assert second.get_signal("000021") == (
        {"code": "000021", "macd_state": "DIF位于DEA上方"},
        "2026-07-21T09:42:00+08:00",
    )
    assert second.get_news("000021") == (
        [{"title": "公开新闻", "url": "https://example.test/news/000021"}],
        "2026-07-21T09:43:00+08:00",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1


def test_file_research_cache_recovers_from_a_corrupt_file(tmp_path) -> None:
    path = tmp_path / "research-last-success.json"
    path.write_text("{broken", encoding="utf-8")

    store = research_cache.FileResearchCacheStore(path)

    assert store.get_signal("000021") is None
    assert store.get_news("000021") is None
    store.put_signal(
        "000021",
        {"code": "000021"},
        "2026-07-21T09:42:00+08:00",
    )
    assert json.loads(path.read_text(encoding="utf-8"))["signals"]["000021"]
