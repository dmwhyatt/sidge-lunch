from sidge_lunch import walking


def test_slug():
    assert walking.slug("Gonville & Caius College") == "gonville-and-caius-college"
    assert walking.slug("Queens' College") == "queens-college"
    assert walking.slug("Café Aristo") == "cafe-aristo"


def test_site_times_batches_and_limits_radius(monkeypatch):
    buildings = [{"id": f"b{i}", "lat": 52.2, "lng": 0.11} for i in range(3)]
    near = [{"id": f"v{i}", "lat": 52.2 + i * 5e-5, "lng": 0.11} for i in range(150)]
    far = [{"id": "far", "lat": 52.3, "lng": 0.11}]  # ~11 km away: never routed
    calls = []

    def fake_table(sources, destinations):
        calls.append((len(sources), len(destinations)))
        assert len(sources) + len(destinations) <= walking.MAX_COORDS
        assert all(d["id"] != "far" for d in destinations)
        return [[60.0] * len(destinations)] * len(sources), [[80.0] * len(destinations)] * len(sources)

    monkeypatch.setattr(walking, "table", fake_table)
    times = walking.site_times(buildings, near + far, pause=0)
    assert len(calls) == 2  # 150 destinations in batches of 97
    assert times["b0"]["v0"] == [60, 80]
    assert len(times["b2"]) == 150 and "far" not in times["b2"]


def test_main_leaves_unchanged_sites_alone(tmp_path, monkeypatch):
    import json

    (tmp_path / "sites.json").write_text(json.dumps({"sites": [
        {"id": "same", "buildings": [{"id": "b", "lat": 52.2, "lng": 0.11}]},
        {"id": "new", "buildings": [{"id": "b", "lat": 52.2, "lng": 0.11}]},
    ]}))
    (tmp_path / "vendors.json").write_text(json.dumps({"vendors": []}))
    (tmp_path / "walking").mkdir()
    old = '{"generated_at":"2026-01-01T00:00:00+00:00","times":{"b":{"v":[60,80]}}}\n'
    (tmp_path / "walking" / "same.json").write_text(old)
    monkeypatch.setattr(walking, "site_times", lambda buildings, vendors: {"b": {"v": [60, 80]}})
    monkeypatch.setattr(walking, "PAUSE", 0)

    walking.main(["--data-dir", str(tmp_path)])
    assert (tmp_path / "walking" / "same.json").read_text() == old
    assert json.loads((tmp_path / "walking" / "new.json").read_text())["times"] == {"b": {"v": [60, 80]}}
