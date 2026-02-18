#!/usr/bin/env python3
"""Parse the King Arthur Baking ingredient weight chart HTML and seed the database."""

import os
import re
import sys

from bs4 import BeautifulSoup

from conversions import parse_fraction, parse_range, parse_volume_text, normalize_to_grams_per_cup
from database import get_db, init_db

HTML_PATH = os.path.join(os.path.dirname(__file__),
                         "Ingredient Weight Chart _ King Arthur Baking.html")


def parse_html(path):
    """Parse the King Arthur HTML file and yield ingredient dicts."""
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    table = soup.find("table", class_="cols-4")
    if not table:
        print("ERROR: Could not find ingredient table in HTML")
        sys.exit(1)

    rows = table.find("tbody").find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) != 4:
            continue

        # Extract text, stripping links/spans
        name = cells[0].get_text(strip=True)
        volume_text = cells[1].get_text(strip=True)
        ounces_text = cells[2].get_text(strip=True)
        grams_text = cells[3].get_text(strip=True)

        # Clean soft hyphens
        name = name.replace("\u00ad", "")
        volume_text = volume_text.replace("\u00ad", "")

        # Parse volume
        volume_amount, volume_unit = parse_volume_text(volume_text)

        # Parse ounces (may be range like "5 to 6")
        ounces = parse_range(ounces_text)

        # Parse grams (may be range like "140 to 170")
        grams = parse_range(grams_text)

        # Compute grams_per_cup
        grams_per_cup = None
        if volume_amount and volume_unit and grams:
            grams_per_cup = normalize_to_grams_per_cup(volume_amount, volume_unit, grams)

        yield {
            "name": name,
            "volume_amount": volume_amount,
            "volume_unit": volume_unit,
            "ounces": ounces,
            "grams": grams,
            "grams_per_cup": grams_per_cup,
        }


def seed():
    init_db()
    db = get_db()

    # Check if already seeded
    count = db.execute("SELECT COUNT(*) FROM ingredient").fetchone()[0]
    if count > 0:
        print(f"Ingredient table already has {count} rows. Skipping seed.")
        db.close()
        return

    inserted = 0
    skipped = 0
    for ing in parse_html(HTML_PATH):
        try:
            db.execute(
                """INSERT INTO ingredient (name, volume_amount, volume_unit, ounces, grams,
                   grams_per_cup, unit_type)
                   VALUES (?, ?, ?, ?, ?, ?, 'volume')""",
                (ing["name"], ing["volume_amount"], ing["volume_unit"],
                 ing["ounces"], ing["grams"], ing["grams_per_cup"]),
            )
            inserted += 1
        except Exception as e:
            skipped += 1
            print(f"  Skipped '{ing['name']}': {e}")

    db.commit()

    # Verify
    total = db.execute("SELECT COUNT(*) FROM ingredient").fetchone()[0]
    flour = db.execute(
        "SELECT grams_per_cup FROM ingredient WHERE name = 'All-Purpose Flour'"
    ).fetchone()

    print(f"Seeded {inserted} ingredients ({skipped} skipped). Total in DB: {total}")
    if flour:
        print(f"  All-Purpose Flour → grams_per_cup = {flour[0]}")

    db.close()


if __name__ == "__main__":
    seed()
