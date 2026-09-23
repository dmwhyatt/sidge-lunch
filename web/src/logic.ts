import type { Allergen, Day, Dietary, Meal, MenuItem, Place, VendorMenu, Walk } from "./types";

export function londonToday(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }).format(now);
}

export function todaysDay(menu: VendorMenu | undefined, today: string): Day | undefined {
  return menu?.days.find((d) => d.date === today);
}

// Straight-line distance, stretched to allow for paths not being straight.
const DETOUR = 1.3;
const WALK_SPEED = 1.3; // m/s, about 4.7 km/h

function haversine(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6371000;
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Routed walk from a building if one was precomputed, else a straight-line estimate. */
export function walkFor(routes: Record<string, [number, number]> | undefined, from: Place, vendor: Place): Walk {
  const routed = routes?.[vendor.id];
  if (routed) return { seconds: routed[0], metres: routed[1], estimated: false };
  const metres = haversine(from, vendor) * DETOUR;
  return { metres: Math.round(metres), seconds: Math.round(metres / WALK_SPEED), estimated: true };
}

export interface Filters {
  dietary: Dietary[]; // item must carry every selected tag
  excludeAllergens: Allergen[]; // hide items the vendor lists as containing any of these
  maxPrice: number | null; // null = any price
  includeUnpriced: boolean;
  lunchOnly: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  dietary: [],
  excludeAllergens: [],
  maxPrice: null,
  includeUnpriced: true,
  lunchOnly: true,
};

const LUNCHY = /lunch|brunch|midday/i;

export function itemMatches(item: MenuItem, f: Filters): boolean {
  if (!f.dietary.every((t) => item.dietary.includes(t))) return false;
  if (f.excludeAllergens.some((a) => item.allergens.includes(a))) return false;
  if (item.price === null) return f.includeUnpriced;
  return f.maxPrice === null || item.price.amount <= f.maxPrice;
}

/** The meals to show for a day, with items filtered. Meals with no matching items are dropped. */
export function filterMeals(day: Day | undefined, f: Filters): Meal[] {
  if (!day) return [];
  const meals = f.lunchOnly && day.meals.some((m) => LUNCHY.test(m.name))
    ? day.meals.filter((m) => LUNCHY.test(m.name))
    : day.meals;
  return meals
    .map((m) => ({ ...m, items: m.items.filter((i) => itemMatches(i, f)) }))
    .filter((m) => m.items.length > 0);
}

export function cheapest(meals: Meal[]): number | null {
  const prices = meals.flatMap((m) => m.items).flatMap((i) => (i.price ? [i.price.amount] : []));
  return prices.length ? Math.min(...prices) : null;
}

export function formatWalk(w: Walk): string {
  const mins = Math.max(1, Math.round(w.seconds / 60));
  const dist = w.metres < 1000 ? `${Math.round(w.metres / 10) * 10} m` : `${(w.metres / 1000).toFixed(1)} km`;
  return `${w.estimated ? "≈" : ""}${mins} min walk · ${dist}`;
}

export function timeAgo(iso: string, now = new Date()): string {
  const s = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400 * 1.5) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}
