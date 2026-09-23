// Snapshot of OpenStreetMap data for central Cambridge, used to build data/sites.json
// and data/places.json. Run by .github/workflows/osm.yml when this file changes.
[out:json][timeout:180][bbox:52.170,0.060,52.240,0.180];
(
  nwr["amenity"~"^(cafe|restaurant|fast_food|pub|food_court|canteen)$"];
  nwr["shop"~"^(bakery|deli|sandwiches)$"];
)->.food;
.food out center tags;
(
  wr["amenity"="university"]["name"];
  wr["amenity"="college"]["name"];
  wr["name"~"^(Cambridge Biomedical Campus|Addenbrooke's Hospital)$"];
)->.campus;
.campus out geom tags;
.campus map_to_area->.areas;
nwr(area.areas)["building"]["name"];
out center tags;
