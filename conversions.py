"""Unit conversion math and fraction formatting."""

import re
from fractions import Fraction

# Volume units → cups multiplier
TO_CUPS = {
    "cup": 1, "cups": 1,
    "tbsp": 1 / 16, "tablespoon": 1 / 16, "tablespoons": 1 / 16,
    "tsp": 1 / 48, "teaspoon": 1 / 48, "teaspoons": 1 / 48,
}

# Unicode fraction characters
UNICODE_FRACTIONS = {
    "¼": 0.25, "½": 0.5, "¾": 0.75,
    "⅓": 1 / 3, "⅔": 2 / 3,
    "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}

# For display: decimal → unicode
DISPLAY_FRACTIONS = [
    (0.25, "¼"), (1 / 3, "⅓"), (0.5, "½"),
    (2 / 3, "⅔"), (0.75, "¾"),
    (0.125, "⅛"), (0.375, "⅜"), (0.625, "⅝"), (0.875, "⅞"),
]


def parse_fraction(text):
    """Parse a string like '4 1/4', '1/2', '3 3/8', '2.5' into a float."""
    text = text.strip()

    # Replace unicode fractions
    for uf, val in UNICODE_FRACTIONS.items():
        if uf in text:
            text = text.replace(uf, "")
            base = float(text.strip()) if text.strip() else 0
            return base + val

    # "4 1/4" → 4.25
    match = re.match(r"^(\d+)\s+(\d+)/(\d+)$", text)
    if match:
        return int(match.group(1)) + int(match.group(2)) / int(match.group(3))

    # "1/2" → 0.5
    match = re.match(r"^(\d+)/(\d+)$", text)
    if match:
        return int(match.group(1)) / int(match.group(2))

    # plain number
    try:
        return float(text)
    except ValueError:
        return None


def parse_range(text):
    """Parse '121 to 150' → average. Otherwise parse as single value."""
    text = text.strip()
    match = re.match(r"^([\d./\s]+)\s+to\s+([\d./\s]+)$", text)
    if match:
        lo = parse_fraction(match.group(1))
        hi = parse_fraction(match.group(2))
        if lo is not None and hi is not None:
            return (lo + hi) / 2
    return parse_fraction(text)


def format_amount(n):
    """Format a number with nice fractions: 1.5 → '1 ½', 0.25 → '¼'."""
    if n is None:
        return ""
    if n == int(n):
        return str(int(n))

    base = int(n)
    frac = n - base
    for val, symbol in DISPLAY_FRACTIONS:
        if abs(frac - val) < 0.05:
            return f"{base} {symbol}" if base else symbol

    # Fallback to decimal
    return f"{n:.1f}" if n % 1 != 0 else str(int(n))


def to_weight(amount, unit, grams_per_cup):
    """Convert a volume amount to grams using density."""
    if amount is None or grams_per_cup is None:
        return None
    unit_lower = unit.lower() if unit else ""
    factor = TO_CUPS.get(unit_lower)
    if factor is None:
        return None
    return round(amount * factor * grams_per_cup)


def normalize_to_grams_per_cup(volume_amount, volume_unit, grams):
    """Given a measurement (e.g. 2 tablespoons = 14g), compute grams per cup."""
    if volume_amount is None or grams is None:
        return None
    unit_lower = volume_unit.lower() if volume_unit else ""
    factor = TO_CUPS.get(unit_lower)
    if factor is None:
        return None
    cups = volume_amount * factor
    if cups == 0:
        return None
    return round(grams / cups, 1)


def parse_volume_text(text):
    """Parse volume text like '1 cup', '2 tablespoons', '8 table­spoons (1/2 cup)'.
    Returns (amount, unit). Prefers cup measurement if parenthetical cup is present."""
    text = text.replace("\u00ad", "").strip()  # remove soft hyphens

    # Check for parenthetical cup: "8 tablespoons (1/2 cup)"
    paren_match = re.search(r"\(([^)]+cup[^)]*)\)", text, re.IGNORECASE)
    if paren_match:
        inner = paren_match.group(1).strip()
        amount_match = re.match(r"^([\d\s/]+)\s*(cup)", inner, re.IGNORECASE)
        if amount_match:
            amt = parse_fraction(amount_match.group(1))
            if amt is not None:
                return amt, "cup"

    # Standard: "1 cup", "2 tablespoons", "1/4 cup"
    match = re.match(r"^([\d\s/.]+)\s+(\w+)", text)
    if match:
        amt = parse_fraction(match.group(1))
        unit = match.group(2).lower()
        # Normalize unit names
        if unit in ("tablespoon", "tablespoons"):
            unit = "tablespoons"
        elif unit in ("teaspoon", "teaspoons"):
            unit = "teaspoons"
        elif unit in ("cup", "cups"):
            unit = "cup"
        return amt, unit

    return None, None
