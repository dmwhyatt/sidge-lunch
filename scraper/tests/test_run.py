from datetime import date, datetime

import pytest

from sidge_lunch import run
from sidge_lunch.schema import Day, Meal, MenuItem, Price

TODAY = date(2026, 9, 23)
NOW = datetime(2026, 9, 23, 9, 0)
VENDOR = {"id": "test", "menu_url": "https://example.org/menu"}


def adapter_returning(days):
    return lambda html, today: days


@pytest.fixture
def register(monkeypatch):
    def _register(adapter):
        monkeypatch.setitem(run.ADAPTERS, "test", adapter)
    return _register


def lunch(*names):
    return Meal("Lunch", [MenuItem(n, price=Price(4.5), price_text="£4.50") for n in names])


def fetcher(url):
    return "<html></html>"


def test_new_menu_sets_updated_at(register):
    register(adapter_returning([Day(TODAY, [lunch("Soup")])]))
    e = run.update_vendor(VENDOR, None, TODAY, NOW, fetcher)
    assert e["status"] == "ok"
    assert e["updated_at"] == "2026-09-23T09:00:00"
    assert e["days"][0]["meals"][0]["items"][0]["name"] == "Soup"


def test_unchanged_menu_keeps_updated_at(register):
    register(adapter_returning([Day(TODAY, [lunch("Soup")])]))
    first = run.update_vendor(VENDOR, None, TODAY, NOW, fetcher)
    later = datetime(2026, 9, 23, 11, 0)
    second = run.update_vendor(VENDOR, first, TODAY, later, fetcher)
    assert second == first


def test_changed_menu_bumps_updated_at(register):
    register(adapter_returning([Day(TODAY, [lunch("Soup")])]))
    first = run.update_vendor(VENDOR, None, TODAY, NOW, fetcher)
    register(adapter_returning([Day(TODAY, [lunch("Curry")])]))
    later = datetime(2026, 9, 23, 11, 0)
    second = run.update_vendor(VENDOR, first, TODAY, later, fetcher)
    assert second["updated_at"] == "2026-09-23T11:00:00"


def test_error_keeps_last_good_menu_and_drops_past_days(register):
    register(adapter_returning([Day(date(2026, 9, 22), [lunch("Old")]), Day(TODAY, [lunch("Soup")])]))
    first = run.update_vendor(VENDOR, None, date(2026, 9, 22), NOW, fetcher)

    def broken(html, today):
        raise ValueError("layout changed")

    register(broken)
    e = run.update_vendor(VENDOR, first, TODAY, NOW, fetcher)
    assert e["status"] == "error"
    assert "layout changed" in e["error"]
    assert [d["date"] for d in e["days"]] == ["2026-09-23"]
    assert e["updated_at"] == first["updated_at"]


def test_unwritten_adapter_is_unsupported(register):
    def stub(html, today):
        raise NotImplementedError

    register(stub)
    e = run.update_vendor(VENDOR, None, TODAY, NOW, fetcher)
    assert e["status"] == "unsupported"
    assert e["days"] == []


def test_vegan_implies_vegetarian():
    assert MenuItem("Dal", dietary=["vegan"]).dietary == ["vegan", "vegetarian"]


def test_unknown_dietary_tag_rejected():
    with pytest.raises(ValueError):
        MenuItem("Stew", dietary=["keto"])


def test_link_only_vendors_are_never_fetched(tmp_path, monkeypatch):
    import json

    (tmp_path / "vendors.json").write_text(json.dumps({"vendors": [
        {"id": "queens", "name": "Q", "menu_url": "https://example.org", "lat": 0, "lng": 0, "link_only": True},
    ]}))
    (tmp_path / "menus.json").write_text(json.dumps({"vendors": {}}))

    def no_fetch(*a, **k):
        raise AssertionError("link-only vendor was fetched")

    monkeypatch.setattr(run, "update_vendor", no_fetch)
    run.main(["--data-dir", str(tmp_path)])
    assert json.loads((tmp_path / "menus.json").read_text()) == {"vendors": {}}


def test_fetch_url_gets_todays_date(register):
    register(adapter_returning([Day(TODAY, [lunch("Soup")])]))
    seen = []
    vendor = {"id": "test", "menu_url": "https://example.org/menu", "fetch_url": "https://example.org/m?date={date}"}
    run.update_vendor(vendor, None, TODAY, NOW, lambda url: seen.append(url) or "")
    assert seen == ["https://example.org/m?date=2026-09-23"]


def test_fetch_url_gets_time_of_run(register):
    register(adapter_returning([Day(TODAY, [lunch("Soup")])]))
    seen = []
    vendor = {"id": "test", "menu_url": "https://example.org/menu", "fetch_url": "https://example.org/menu?t={now}"}
    run.update_vendor(vendor, None, TODAY, NOW, lambda url: seen.append(url) or "")
    assert seen == [f"https://example.org/menu?t={NOW:%Y%m%d%H%M}"]


def _menus_dir(tmp_path, prev):
    import json

    (tmp_path / "vendors.json").write_text(json.dumps({"vendors": [
        {"id": "test", "name": "T", "menu_url": "https://example.org/menu", "lat": 0, "lng": 0},
    ]}))
    (tmp_path / "menus.json").write_text(json.dumps({"vendors": {"test": prev} if prev else {}}))


def _today_entry(status="ok", day=None):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    day = day or datetime.now(ZoneInfo("Europe/London")).date().isoformat()
    return {"source_url": "u", "status": status, "error": None, "updated_at": None, "content_hash": "h",
            "days": [{"date": day, "meals": []}]}


@pytest.mark.parametrize("prev, argv, fetched", [
    (_today_entry(), [], False),                        # today's menu already in: skipped
    (_today_entry(), ["--force"], True),                # --force scrapes anyway
    (_today_entry(), ["--only", "test"], True),         # naming the vendor scrapes it
    (_today_entry(status="error"), [], True),           # last scrape failed: try again
    (_today_entry(day="2000-01-01"), [], True),         # only an old menu: try again
    (None, [], True),                                   # never scraped
])
def test_skips_vendors_that_already_have_todays_menu(tmp_path, monkeypatch, prev, argv, fetched):
    _menus_dir(tmp_path, prev)
    calls = []
    monkeypatch.setattr(run, "update_vendor", lambda v, p, *a, **k: calls.append(v["id"]) or (p or {"status": "ok"}))
    run.main(["--data-dir", str(tmp_path), *argv])
    assert (calls == ["test"]) is fetched
