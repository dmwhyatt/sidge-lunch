"""Adapters against saved copies of each vendor's page (tests/fixtures/, fetched 2026-09-23)."""

from datetime import date
from pathlib import Path

import pytest

from sidge_lunch.adapters import ADAPTERS

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 9, 23)


def parse(vendor):
    return [d.to_json() for d in ADAPTERS[vendor]((FIXTURES / f"{vendor}.html").read_text(), TODAY)]


def items(day, meal="Lunch"):
    return {i["name"]: i for m in day["meals"] if m["name"] == meal for i in m["items"]}


def test_newnham():
    [day] = parse("newnham")
    assert day["date"] == "2026-09-23"
    lunch = items(day)
    biryani = lunch["Mushroom, Cauliflower & Vegetable Biryani"]
    assert biryani["dietary"] == ["vegan", "vegetarian"]
    assert biryani["allergens"] == ["mustard", "sulphites"]
    assert biryani["price"] == {"amount": 4.79, "currency": "GBP"}
    assert biryani["price_text"] == "£4.79"
    assert biryani["description"] == "£3.60 with a Newnham card"
    assert lunch["Squash, Red Onion & Goats Cheese Quiche"]["allergens"] == ["eggs", "gluten", "milk"]
    assert lunch["Halal Roast Turkey Breast with Cranberry Sauce"]["dietary"] == ["halal"]
    deal = lunch["Hot Meal Deal"]
    assert deal["price"] is None and deal["allergens"] == []
    assert deal["description"].startswith("Vegan/Vegetarian + 1 Side £4.50 (Non-Members £6.00); Meat/Fish")


def test_selwyn():
    [day] = parse("selwyn")
    assert day["date"] == "2026-09-23"
    assert [m["name"] for m in day["meals"]] == ["Lunch", "Dinner"]
    lunch_meal = day["meals"][0]
    assert lunch_meal["note"] == "Halal option available"
    lunch = items(day)
    assert list(lunch) == [
        "Jackfruit bulgogi stir-fry", "Fish paella", "Butter chicken curry",
        "Pork ribs", "Lentil sweet potato dhal", "Sides",
    ]
    assert lunch["Jackfruit bulgogi stir-fry"]["dietary"] == ["vegan", "vegetarian"]
    assert lunch["Fish paella"]["dietary"] == []
    assert all(i["price"] is None for i in lunch.values())
    assert lunch["Sides"]["description"].startswith("Fries, Bombay potatoes")


def test_darwin():
    days = parse("darwin")
    assert [d["date"] for d in days] == [
        "2026-09-23", "2026-09-24", "2026-09-25",  # this week, from today
        "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02",  # next week
    ]
    lunch = items(days[0])
    bao = lunch["Oyster mushroom Bao buns, chipotle crema, pickled lime shallots"]
    assert bao["price"] == {"amount": 2.95, "currency": "GBP"}
    assert bao["allergens"] == ["eggs", "gluten", "soya", "sulphites"]
    assert bao["dietary"] == []  # Darwin publishes allergens, not dietary labels
    assert lunch["Sides"]["description"].startswith("Braised basmati rice")
    assert [m["name"] for m in days[0]["meals"]] == ["Lunch", "Dinner"]

    friday_dinner = items(days[2], "Dinner")
    assert friday_dinner["Chicken goulash, soured cream"]["dietary"] == ["halal"]
    assert "(halal)" not in "".join(friday_dinner)
    note = next(m["note"] for m in days[2]["meals"] if m["name"] == "Dinner")
    assert note == "See daily boards for specials and allergens"

def test_the_mill():
    [day] = parse("the-mill")
    assert day["date"] == "2026-09-23"  # a regular menu is reported as today's
    [meal] = day["meals"]
    by_name = {i["name"]: i for i in meal["items"]}
    soup = by_name["Watercress, pea & mint soup"]
    assert soup["price"] == {"amount": 9.0, "currency": "GBP"}
    assert soup["price_text"] == "£9.00"
    assert soup["description"] == "Creme fresh & Sourdough"
    assert soup["dietary"] == ["vegetarian"]
    assert soup["category"] == "Small Plates"
    assert by_name["Pan fried Gressingham duck breast"]["dietary"] == []
    assert any(i["dietary"] == ["vegan", "vegetarian"] for i in meal["items"])
    assert {i["category"] for i in meal["items"]} >= {"Sides", "Mains", "Puddings"}


def test_st_johns():
    [day] = parse("st-johns")
    assert day["date"] == "2026-09-23"
    [dinner] = day["meals"]
    assert dinner["name"] == "Dinner"
    dishes = {i["name"]: i for i in dinner["items"]}
    soup = dishes["Sweetcorn soup with chimicurri"]
    assert soup["category"] == "Starter"
    assert soup["dietary"] == ["vegan", "vegetarian"]
    assert soup["allergens"] == ["celery", "sulphites"]
    korma = dishes["Quorn korma, toasted almonds, coriander and yogurt"]
    assert korma["allergens"] == ["milk", "mustard", "nuts", "soya"]  # "Nuts (almonds)"
    assert all(i["price"] is None for i in dinner["items"])


def test_robinson():
    [day] = parse("robinson")
    assert day["date"] == "2026-09-23"
    [lunch] = day["meals"]
    assert lunch["name"] == "Lunch"
    assert "£6.30 / £8.30" in lunch["note"]
    mac, sausage = lunch["items"][:2]
    assert mac == {"name": "Macaroni cheese", "description": None, "category": "Main Courses", "price": None,
                   "price_text": None, "dietary": ["vegetarian"], "allergens": ["milk", "mustard"]}
    assert sausage["name"] == "Braised Cumberland sausage chasseur"
    assert sausage["allergens"] == ["celery", "gluten", "sulphites"]


def test_churchill():
    days = parse("churchill")
    by_date = {d["date"]: d for d in days}
    assert "2026-09-24" not in by_date  # "*" only: not published yet
    wed = by_date["2026-09-23"]
    lunch = {i["name"]: i for i in wed["meals"][0]["items"]}
    assert wed["meals"][0]["name"] == "Lunch"
    assert lunch["Lentil Dhal"]["dietary"] == ["vegan", "vegetarian"]
    assert lunch["Gremolata Chicken"]["dietary"] == ["halal"]
    assert lunch["Beef Chilli"]["dietary"] == []
    assert [m["name"] for m in wed["meals"]] == ["Lunch", "Dinner"]


def test_corpus():
    [day] = parse("corpus")
    assert [m["name"] for m in day["meals"]] == ["Breakfast", "Lunch", "Dinner"]
    lunch = {i["name"]: i for i in day["meals"][1]["items"]}
    samosas = lunch["Vegetable samosas plant based Raita"]
    assert samosas["category"] == "Plant Based"
    assert samosas["dietary"] == ["vegan", "vegetarian"]
    assert samosas["price"] == {"amount": 2.9, "currency": "GBP"}
    assert samosas["allergens"] == ["gluten", "soya", "sulphites"]
    fish = lunch["Catch of the day with samphire and butter sauce"]
    assert fish["category"] == "Meat/Fish" and fish["dietary"] == []
    assert lunch["Steamed summer greens"]["price_text"] == "£0.95"  # written "£.95"
    breakfast = {i["name"]: i for i in day["meals"][0]["items"]}
    assert breakfast["Variety of hot breads"]["price"] is None  # "£0.00": not a real price


@pytest.mark.parametrize("vendor", ["newnham", "selwyn", "darwin", "the-mill", "st-johns", "robinson", "corpus", "churchill"])
def test_rejects_unrelated_page(vendor):
    with pytest.raises(ValueError):
        ADAPTERS[vendor]("<html><body><p>Page not found</p></body></html>", TODAY)
