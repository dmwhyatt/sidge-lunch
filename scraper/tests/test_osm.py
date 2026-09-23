import json

from sidge_lunch import osm


def test_sync_sets_coordinates_from_osm(tmp_path, monkeypatch):
    (tmp_path / "vendors.json").write_text(json.dumps({"vendors": [
        {"id": "a", "osm": "way/1", "lat": 0, "lng": 0},
        {"id": "b", "lat": 5, "lng": 5},  # no osm id: left alone
    ]}))
    queries = []

    def fake_overpass(q):
        queries.append(q)
        return [{"type": "way", "id": 1, "center": {"lat": 52.2001234, "lon": 0.1101234}}]

    monkeypatch.setattr(osm, "overpass", fake_overpass)
    osm.sync(tmp_path)

    vendors = json.loads((tmp_path / "vendors.json").read_text())["vendors"]
    assert vendors[0] == {"id": "a", "osm": "way/1", "lat": 52.200123, "lng": 0.110123}
    assert vendors[1] == {"id": "b", "lat": 5, "lng": 5}
    assert "way(id:1);" in queries[0]
