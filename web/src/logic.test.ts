import { describe, expect, it } from "vitest";
import { DEFAULT_FILTERS, cheapest, filterMeals, formatWalk, londonToday, walkFor } from "./logic";
import type { Day, MenuItem } from "./types";

const item = (name: string, price: number | null, dietary: MenuItem["dietary"] = []): MenuItem => ({
  name,
  description: null,
  category: null,
  price: price === null ? null : { amount: price, currency: "GBP" },
  price_text: price === null ? null : `£${price.toFixed(2)}`,
  dietary,
});

const day: Day = {
  date: "2026-09-23",
  meals: [
    { name: "Lunch", service: "12:00–13:45", items: [item("Dal", 3.5, ["vegan", "vegetarian"]), item("Steak pie", 6), item("Bread", null)] },
    { name: "Dinner", service: null, items: [item("Risotto", 5, ["vegetarian"])] },
  ],
};

describe("filterMeals", () => {
  it("shows lunch only by default", () => {
    expect(filterMeals(day, DEFAULT_FILTERS).map((m) => m.name)).toEqual(["Lunch"]);
  });

  it("shows all meals when lunch-only is off", () => {
    expect(filterMeals(day, { ...DEFAULT_FILTERS, lunchOnly: false }).map((m) => m.name)).toEqual(["Lunch", "Dinner"]);
  });

  it("falls back to all meals if none is called lunch", () => {
    const d: Day = { ...day, meals: [day.meals[1]] };
    expect(filterMeals(d, DEFAULT_FILTERS).map((m) => m.name)).toEqual(["Dinner"]);
  });

  it("requires every selected dietary tag", () => {
    const names = filterMeals(day, { ...DEFAULT_FILTERS, dietary: ["vegan", "vegetarian"] })[0].items.map((i) => i.name);
    expect(names).toEqual(["Dal"]);
  });

  it("applies max price and the unpriced toggle", () => {
    const f = { ...DEFAULT_FILTERS, maxPrice: 4 };
    expect(filterMeals(day, f)[0].items.map((i) => i.name)).toEqual(["Dal", "Bread"]);
    expect(filterMeals(day, { ...f, includeUnpriced: false })[0].items.map((i) => i.name)).toEqual(["Dal"]);
  });

  it("drops meals with nothing left", () => {
    expect(filterMeals(day, { ...DEFAULT_FILTERS, dietary: ["halal"] })).toEqual([]);
  });
});

describe("helpers", () => {
  it("finds the cheapest priced item", () => {
    expect(cheapest(filterMeals(day, DEFAULT_FILTERS))).toBe(3.5);
  });

  it("uses London date", () => {
    // 23:30 UTC in summer is already the next day in London
    expect(londonToday(new Date("2026-07-01T23:30:00Z"))).toBe("2026-07-02");
  });

  it("prefers routed times and marks estimates", () => {
    const fac = { id: "f", name: "F", building: "B", lat: 52.2016, lng: 0.1089 };
    const ven = { id: "v", name: "V", menu_url: "", lat: 52.2009, lng: 0.1059 };
    expect(walkFor({ source: "x", generated_at: null, times: { f: { v: { seconds: 300, metres: 400 } } } }, fac, ven)).toEqual({
      seconds: 300,
      metres: 400,
      estimated: false,
    });
    const est = walkFor({ source: null, generated_at: null, times: {} }, fac, ven);
    expect(est.estimated).toBe(true);
    expect(formatWalk(est)).toMatch(/^≈\d+ min walk · \d+ m$/);
  });
});
