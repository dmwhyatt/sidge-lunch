import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./style.css";
import {
  DEFAULT_FILTERS,
  cheapest,
  filterMeals,
  formatWalk,
  londonToday,
  timeAgo,
  todaysDay,
  walkFor,
  type Filters,
} from "./logic";
import { ALLERGENS, VENDOR_TYPES, VENDOR_TYPE_LABELS, type Allergen, type VendorType } from "./types";
import type { Building, Dietary, Meal, Site, SiteWalking, Vendor, VendorMenu, Walk } from "./types";

const DIETARY_ABBR: Record<Dietary, string> = {
  vegan: "VG",
  vegetarian: "V",
  "gluten-free": "GF",
  "dairy-free": "DF",
  halal: "H",
};
const WHERE_KEY = "sidge-lunch:where";
const DEFAULT_WHERE = { site: "sidgwick", building: "faculty-of-english" };

interface Data {
  vendors: Vendor[]; // hand-curated first, then generated places
  sites: Site[];
  menus: Record<string, VendorMenu>;
}

interface Row {
  vendor: Vendor;
  menu: VendorMenu | undefined;
  walk: Walk;
  meals: Meal[];
  hasToday: boolean;
}

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

async function getJson<T>(name: string): Promise<T> {
  const r = await fetch(`${import.meta.env.BASE_URL}${name}`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

async function load(): Promise<Data> {
  const [curated, places, sites, menus] = await Promise.all([
    getJson<{ vendors: Vendor[] }>("vendors.json"),
    getJson<{ vendors: Vendor[] }>("places.json").catch(() => ({ vendors: [] as Vendor[] })),
    getJson<{ sites: Site[] }>("sites.json"),
    getJson<{ vendors: Record<string, VendorMenu> }>("menus.json"),
  ]);
  return { vendors: [...curated.vendors, ...places.vendors], sites: sites.sites, menus: menus.vendors };
}

const walkingCache = new Map<string, Promise<SiteWalking | null>>();
function siteWalking(siteId: string): Promise<SiteWalking | null> {
  if (!walkingCache.has(siteId)) {
    walkingCache.set(siteId, getJson<SiteWalking>(`walking/${siteId}.json`).catch(() => null));
  }
  return walkingCache.get(siteId)!;
}

function storedWhere(sites: Site[]): { site: Site; building: Building } {
  let want = DEFAULT_WHERE;
  try {
    want = { ...want, ...JSON.parse(localStorage.getItem(WHERE_KEY) ?? "{}") };
  } catch {
    // storage unavailable or garbled; use the default
  }
  const site = sites.find((s) => s.id === want.site) ?? sites[0];
  const building = site.buildings.find((b) => b.id === want.building) ?? site.buildings[0];
  return { site, building };
}

function saveWhere(site: Site, building: Building) {
  try {
    localStorage.setItem(WHERE_KEY, JSON.stringify({ site: site.id, building: building.id }));
  } catch {
    // storage unavailable; the choice just won't persist
  }
}

function readFilters(): Filters & { sort: "walk" | "price"; types: VendorType[]; menuOnly: boolean; range: number } {
  const form = $<HTMLFormElement>("#filters");
  const dietary = [...form.querySelectorAll<HTMLInputElement>('input[name="dietary"]:checked')].map(
    (i) => i.value as Dietary,
  );
  const excludeAllergens = [...form.querySelectorAll<HTMLInputElement>('input[name="allergen"]:checked')].map(
    (i) => i.value as Allergen,
  );
  const range = $<HTMLInputElement>("#max-price");
  const max = Number(range.value);
  return {
    ...DEFAULT_FILTERS,
    dietary,
    excludeAllergens,
    maxPrice: max >= Number(range.max) ? null : max,
    includeUnpriced: $<HTMLInputElement>("#include-unpriced").checked,
    lunchOnly: $<HTMLInputElement>("#lunch-only").checked,
    sort: $<HTMLSelectElement>("#sort").value as "walk" | "price",
    menuOnly: $<HTMLInputElement>("#menu-only").checked,
    range: Number($<HTMLSelectElement>("#range").value) * 60,
    types: [...form.querySelectorAll<HTMLInputElement>('input[name="type"]:checked')].map((i) => i.value as VendorType),
  };
}

function statusLine(row: Row): string {
  if (row.vendor.link_only) return ""; // not scraped; the card links to the vendor instead
  const m = row.menu;
  if (!m || m.status === "unsupported") {
    return `<p class="status">Menu not collected yet. See the vendor's own page.</p>`;
  }
  const updated = m.updated_at ? `updated ${timeAgo(m.updated_at)}` : "never collected";
  if (m.status === "error") {
    return `<p class="status error">Couldn't read the latest menu (last ${updated}). Check the vendor's page.</p>`;
  }
  if (!row.hasToday) return `<p class="status">No menu published for today (${updated}).</p>`;
  if (row.vendor.menu === "regular") {
    const changed = m.updated_at ? `, last changed ${timeAgo(m.updated_at)}` : "";
    return `<p class="status">Regular menu, not a daily one${changed}.</p>`;
  }
  return `<p class="status">Menu ${updated}.</p>`;
}

function mealsHtml(row: Row): string {
  if (!row.hasToday) return "";
  if (row.meals.length === 0) return `<p class="empty">Nothing matches your filters.</p>`;
  return row.meals
    .map(
      (meal) => `
      <div class="meal">
        <h3>${esc(meal.name)}${meal.service ? ` <span>${esc(meal.service)}</span>` : ""}</h3>
        <ul class="items">
          ${meal.items
            .map((item, i) => {
              const category =
                item.category && item.category !== meal.items[i - 1]?.category
                  ? `<li class="category">${esc(item.category)}</li>`
                  : "";
              const chips = item.dietary
                .filter((t) => !(t === "vegetarian" && item.dietary.includes("vegan")))
                .map((t) => `<abbr class="chip" title="${t}">${DIETARY_ABBR[t]}</abbr>`)
                .join("");
              const price = item.price_text
                ? `<span class="item-price">${esc(item.price_text)}</span>`
                : `<span class="item-price unlisted">price not listed</span>`;
              return `${category}<li>
                <span class="item-name">${esc(item.name)}${chips ? `<span class="chips">${chips}</span>` : ""}</span>
                ${price}
                ${item.description ? `<span class="item-desc">${esc(item.description)}</span>` : ""}
                ${item.allergens.length ? `<span class="item-allergens">Contains: ${item.allergens.join(", ")}</span>` : ""}
              </li>`;
            })
            .join("")}
        </ul>
        ${meal.note ? `<p class="meal-note">${esc(meal.note)}</p>` : ""}
      </div>`,
    )
    .join("");
}

function typeTag(type: VendorType): string {
  return `<span class="vendor-type t-${type}"><span class="type-dot"></span>${VENDOR_TYPE_LABELS[type]}</span>`;
}

function sourceLink(row: Row): string {
  const url = row.vendor.menu_url;
  return url ? `<a class="source" href="${esc(url)}" target="_blank" rel="noopener">Vendor's page ↗</a>` : "";
}

function infoHtml(v: Vendor, today: string): string {
  const notice = v.notice && (!v.notice_until || today < v.notice_until) ? v.notice : null;
  return [
    notice ? `<p class="notice">${esc(notice)}</p>` : "",
    v.about ? `<p class="about">${esc(v.about)}</p>` : "",
    v.approx ? `<p class="hours">Map position is approximate.</p>` : "",
    v.hours ? `<p class="hours">Hours: ${esc(v.hours)}</p>` : "",
  ].join("");
}

function buildingLabel(b: Building): string {
  return b.occupants ? `${b.name} (${b.occupants})` : b.name;
}

function main(data: Data) {
  const today = londonToday();
  $("#today").textContent = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  $("#type-options").innerHTML = VENDOR_TYPES.map(
    (t) => `<label class="type-option t-${t}"><input type="checkbox" name="type" value="${t}" checked />
      <span class="type-dot"></span>${VENDOR_TYPE_LABELS[t]}</label>`,
  ).join("");

  $("#allergen-options").innerHTML = ALLERGENS.map(
    (a) => `<label><input type="checkbox" name="allergen" value="${a}" /> ${a}</label>`,
  ).join("");

  // Where am I: site, then building within it.
  const siteSelect = $<HTMLSelectElement>("#site");
  const buildingSelect = $<HTMLSelectElement>("#building");
  const group = (kind: Site["kind"], label: string) =>
    `<optgroup label="${label}">${data.sites
      .filter((s) => s.kind === kind)
      .map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`)
      .join("")}</optgroup>`;
  siteSelect.innerHTML = group("university", "University") + group("college", "Colleges");
  let { site, building } = storedWhere(data.sites);
  let routes: Record<string, [number, number]> | undefined;
  const fillBuildings = () => {
    buildingSelect.innerHTML = site.buildings
      .map((b) => `<option value="${esc(b.id)}">${esc(buildingLabel(b))}</option>`)
      .join("");
  };
  siteSelect.value = site.id;
  fillBuildings();
  buildingSelect.value = building.id;
  let selectedVendor: string | null = null;

  // Map
  const map = L.map("map", { scrollWheelZoom: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  map.setView([building.lat, building.lng], 16);

  const legend = new L.Control({ position: "bottomleft" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "legend");
    div.innerHTML = VENDOR_TYPES.map(
      (t) => `<div class="t-${t}"><span class="type-dot"></span>${VENDOR_TYPE_LABELS[t]}</div>`,
    ).join("");
    return div;
  };
  legend.addTo(map);

  // Zoomed out, link-only places shrink to dots so labels don't pile up; names stay on hover.
  const COMPACT_BELOW = 17;
  const setCompact = () => map.getContainer().classList.toggle("compact", map.getZoom() < COMPACT_BELOW);
  map.on("zoomend", setCompact);
  setCompact();

  const pinIcon = (label: string, cls: string) =>
    L.divIcon({
      className: "pin-host",
      html: `<span class="pin ${cls}"><span class="pin-label">${esc(label)}</span></span>`,
      iconSize: [0, 0],
    });

  const youMarker = L.marker([building.lat, building.lng], {
    icon: pinIcon("You", "faculty"),
    keyboard: false,
    zIndexOffset: -100,
  }).addTo(map);

  // Markers are made when a place first comes into range; hundreds exist in total.
  const vendorMarkers = new Map<string, L.Marker>();
  const markerFor = (v: Vendor) => {
    let m = vendorMarkers.get(v.id);
    if (!m) {
      m = L.marker([v.lat, v.lng], {
        icon: pinIcon(v.name, `t-${v.type}${v.link_only ? " link-only" : ""}`),
        title: v.name,
      });
      m.bindPopup("", { maxWidth: 320, autoPanPadding: [20, 20] });
      m.on("popupopen", () => select_(v.id, false));
      vendorMarkers.set(v.id, m);
    }
    return m;
  };

  function select_(id: string, openPopup: boolean) {
    selectedVendor = id;
    document.querySelectorAll(".vendor").forEach((el) => el.classList.toggle("selected", el.id === `v-${id}`));
    for (const [vid, marker] of vendorMarkers) {
      marker.getElement()?.querySelector(".pin")?.classList.toggle("selected", vid === id);
    }
    // Side by side, keep the card list in step with the map. Stacked (phones), the map
    // sits above the list, so bring the map into view instead of scrolling away from it.
    const sideBySide = window.matchMedia("(min-width: 801px)").matches;
    const marker = vendorMarkers.get(id);
    if (openPopup && marker) {
      marker.openPopup();
      map.panTo(marker.getLatLng());
      if (!sideBySide) $("#map").scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (sideBySide) {
      document.getElementById(`v-${id}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function render(refit = false) {
    const f = readFilters();
    $<HTMLOutputElement>("#max-price-out").textContent = f.maxPrice === null ? "any" : `£${f.maxPrice.toFixed(2)}`;
    $("#allergen-count").textContent = f.excludeAllergens.length ? `(${f.excludeAllergens.length})` : "";

    const rows: Row[] = data.vendors
      .filter((v) => f.types.includes(v.type))
      .map((vendor) => {
        const menu = data.menus[vendor.id];
        const day = todaysDay(menu, today);
        return { vendor, menu, walk: walkFor(routes, building, vendor), meals: filterMeals(day, f), hasToday: !!day };
      })
      .filter((row) => row.walk.seconds <= f.range && (!f.menuOnly || row.hasToday));
    rows.sort((a, b) => {
      // Vendors with matching items today first, then by chosen key.
      const am = a.meals.length > 0 ? 0 : 1;
      const bm = b.meals.length > 0 ? 0 : 1;
      if (am !== bm) return am - bm;
      if (f.sort === "price") {
        const ap = cheapest(a.meals) ?? Infinity;
        const bp = cheapest(b.meals) ?? Infinity;
        if (ap !== bp) return ap - bp;
      }
      return a.walk.seconds - b.walk.seconds;
    });

    const withMenu = rows.filter((r) => r.hasToday).length;
    $("#count").textContent = rows.length
      ? `${rows.length} place${rows.length === 1 ? "" : "s"} within ${f.range / 60} min of ${building.name}` +
        (withMenu ? `, ${withMenu} with a menu today.` : ".")
      : `Nothing within ${f.range / 60} min of ${building.name} matches. Try a longer walk.`;

    $("#vendors").innerHTML = rows
      .map(
        (row) => `
        <article class="vendor${row.vendor.id === selectedVendor ? " selected" : ""}" id="v-${esc(row.vendor.id)}">
          <header>
            <h2><button type="button" data-vendor="${esc(row.vendor.id)}">${esc(row.vendor.name)}</button></h2>
            ${typeTag(row.vendor.type)}
            <span class="walk">${formatWalk(row.walk)}</span>
          </header>
          ${infoHtml(row.vendor, today)}
          ${statusLine(row)}
          ${mealsHtml(row)}
          ${sourceLink(row)}
        </article>`,
      )
      .join("");

    const shown = new Set(rows.map((r) => r.vendor.id));
    for (const [id, marker] of vendorMarkers) if (!shown.has(id)) marker.remove();
    for (const row of rows) {
      const marker = markerFor(row.vendor).addTo(map);
      const el = marker.getElement()?.querySelector(".pin");
      el?.classList.toggle("dim", !row.vendor.link_only && row.meals.length === 0);
      el?.classList.toggle("selected", row.vendor.id === selectedVendor);
      marker.setPopupContent(`
        <div class="vendor-popup">
          <h2>${esc(row.vendor.name)}</h2>
          ${typeTag(row.vendor.type)}
          <div class="walk">${formatWalk(row.walk)} from ${esc(building.name)}</div>
          ${infoHtml(row.vendor, today)}
          ${statusLine(row)}
          ${mealsHtml(row)}
          ${sourceLink(row)}
        </div>`);
    }

    if (refit) {
      const points: L.LatLngExpression[] = [[building.lat, building.lng], ...rows.map((r) => [r.vendor.lat, r.vendor.lng] as L.LatLngTuple)];
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 17 });
    }
  }

  async function moveTo(newSite: Site, newBuilding: Building) {
    site = newSite;
    building = newBuilding;
    saveWhere(site, building);
    youMarker.setLatLng([building.lat, building.lng]);
    routes = undefined;
    render(true);
    const walking = await siteWalking(site.id);
    if (site === newSite && building === newBuilding) {
      routes = walking?.times[building.id];
      $("#walk-source").textContent = walking?.source
        ? `Walking times: ${walking.source}. Times marked ≈ are straight-line estimates.`
        : "Walking times marked ≈ are straight-line estimates.";
      render(true);
    }
  }

  siteSelect.addEventListener("change", () => {
    const s = data.sites.find((x) => x.id === siteSelect.value)!;
    site = s;
    fillBuildings();
    moveTo(s, s.buildings[0]);
  });
  buildingSelect.addEventListener("change", () => {
    moveTo(site, site.buildings.find((b) => b.id === buildingSelect.value)!);
  });
  $("#range").addEventListener("change", () => render(true));
  $("#filters").addEventListener("input", () => render());
  $("#vendors").addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLButtonElement>("button[data-vendor]");
    if (btn) select_(btn.dataset.vendor!, true);
  });

  moveTo(site, building);
}

load().then(main, (err) => {
  $("#vendors").innerHTML = `<p class="status error">Couldn't load menu data: ${esc(String(err))}</p>`;
});
