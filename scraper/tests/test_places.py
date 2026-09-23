from sidge_lunch.places import build


def square(way_id, lat, lng, size, **tags):
    geometry = [{"lat": lat, "lon": lng}, {"lat": lat, "lon": lng + size},
                {"lat": lat + size, "lon": lng + size}, {"lat": lat + size, "lon": lng}, {"lat": lat, "lon": lng}]
    return {"type": "way", "id": way_id, "tags": tags, "geometry": geometry,
            "bounds": {"minlat": lat, "minlon": lng, "maxlat": lat + size, "maxlon": lng + size}}


def node(node_id, lat, lng, **tags):
    return {"type": "node", "id": node_id, "lat": lat, "lon": lng, "tags": tags}


SIDGWICK = square(82608357, 52.200, 0.107, 0.003, amenity="university", name="Sidgwick Site",
                  operator="University of Cambridge")
SELWYN = square(3997883, 52.199, 0.103, 0.002, amenity="university", name="Selwyn College (University of Cambridge)",
                operator="Selwyn College (University of Cambridge)", website="https://www.sel.cam.ac.uk/")
ANNEXE = square(4158025, 52.207, 0.117, 0.001, amenity="university", name="Blue Boar Court (Trinity College)",
                operator="Trinity College (University of Cambridge)")
UL = square(166274631, 52.2055, 0.1075, 0.001, amenity="university", name="Cambridge University Library",
            operator="University of Cambridge")
ELEMENTS = [
    SIDGWICK, SELWYN, ANNEXE, UL,
    node(1, 52.2015, 0.1085, building="yes", name="Faculty of English"),
    node(2, 52.2016, 0.1086, building="yes", name="Custodian's Hut"),  # not a workplace
    node(3, 52.2012, 0.1088, amenity="cafe", name="The Arc", operator="University of Cambridge"),
    node(4, 52.2013, 0.1089, amenity="cafe", name="Costa"),  # on a University site, but not run by it
    node(5, 52.1995, 0.1035, amenity="bar", name="Selwyn Bar"),  # not a food amenity we collect
    node(6, 52.1995, 0.1036, amenity="cafe", name="Selwyn Buttery"),  # inside a college: the college covers it
    node(7, 52.2100, 0.1200, amenity="pub", name="The Eagle", opening_hours="Mo-Su 11:00-23:00",
         website="https://example.org/eagle", cuisine="british"),
    node(8, 52.2101, 0.1201, amenity="canteen", name="Company Canteen"),  # private
    node(9, 52.2102, 0.1202, amenity="cafe", name="Curated Café"),
]


def test_sites_and_buildings():
    sites, _ = build(ELEMENTS + [ELEMENTS[4]], curated=[])  # duplicated elements are ignored
    by_id = {s["id"]: s for s in sites["sites"]}
    assert [b["name"] for b in by_id["sidgwick"]["buildings"]] == ["Faculty of English"]
    assert [b["name"] for b in by_id["other-university"]["buildings"]] == ["Cambridge University Library"]
    assert [b["name"] for b in by_id["colleges"]["buildings"]] == ["Selwyn College"]
    assert [s["id"] for s in sites["sites"]] == ["sidgwick", "other-university", "colleges"]


def test_places():
    curated = [{"id": "curated", "name": "Curated Café", "osm": "node/9"}, {"id": "x", "name": "Selwyn College"}]
    _, places = build(ELEMENTS, curated)
    by_name = {v["name"]: v for v in places["vendors"]}
    assert set(by_name) == {"The Arc", "Costa", "The Eagle"}  # Selwyn and the Curated Café are curated
    assert by_name["The Arc"]["type"] == "university"
    assert by_name["Costa"]["type"] == "commercial"
    eagle = by_name["The Eagle"]
    assert eagle == {"id": "osm-n7", "name": "The Eagle", "type": "commercial", "about": "Pub · british",
                     "osm": "node/7", "lat": 52.21, "lng": 0.12, "link_only": True,
                     "menu_url": "https://example.org/eagle", "hours": "Mo-Su 11:00-23:00"}


def test_colleges_become_link_only_vendors():
    _, places = build(ELEMENTS, curated=[])
    [selwyn] = [v for v in places["vendors"] if v["type"] == "college"]
    assert selwyn["id"] == "college-selwyn-college"
    assert selwyn["menu_url"] == "https://www.sel.cam.ac.uk/"
    assert selwyn["link_only"] is True
