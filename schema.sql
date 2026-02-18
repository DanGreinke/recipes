CREATE TABLE IF NOT EXISTS ingredient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    volume_amount REAL,
    volume_unit TEXT,
    ounces REAL,
    grams REAL,
    grams_per_cup REAL,
    unit_type TEXT NOT NULL DEFAULT 'volume' CHECK (unit_type IN ('volume', 'count', 'both')),
    avg_weight_grams REAL
);

CREATE TABLE IF NOT EXISTS recipe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    image_path TEXT,
    servings INTEGER NOT NULL DEFAULT 4,
    tags TEXT DEFAULT '',
    source_url TEXT
);

CREATE TABLE IF NOT EXISTS recipe_step (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id),
    step_number INTEGER NOT NULL,
    instruction TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_ingredient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipe(id),
    ingredient_id INTEGER REFERENCES ingredient(id),
    name TEXT NOT NULL,
    amount REAL,
    unit TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);
