import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "recipes.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")
RECIPES_PATH = os.path.join(os.path.dirname(__file__), "recipes.json")


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    db = get_db()
    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())
    # Migration: add source_url if missing
    cols = [row[1] for row in db.execute("PRAGMA table_info(recipe)").fetchall()]
    if "source_url" not in cols:
        db.execute("ALTER TABLE recipe ADD COLUMN source_url TEXT")
    db.commit()
    db.close()


# ── Ingredient queries ─────────────────────────────────────────────────────

def get_all_ingredients(db):
    return db.execute("SELECT * FROM ingredient ORDER BY name COLLATE NOCASE").fetchall()


def get_ingredient_by_id(db, ingredient_id):
    return db.execute("SELECT * FROM ingredient WHERE id = ?", (ingredient_id,)).fetchone()


def get_ingredient_by_name(db, name):
    return db.execute("SELECT * FROM ingredient WHERE name = ? COLLATE NOCASE", (name,)).fetchone()


def insert_ingredient(db, name, volume_amount, volume_unit, ounces, grams,
                      grams_per_cup, unit_type="volume", avg_weight_grams=None):
    db.execute(
        """INSERT INTO ingredient (name, volume_amount, volume_unit, ounces, grams,
           grams_per_cup, unit_type, avg_weight_grams)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, volume_amount, volume_unit, ounces, grams,
         grams_per_cup, unit_type, avg_weight_grams),
    )
    db.commit()


def update_ingredient(db, ingredient_id, name, volume_amount, volume_unit,
                      ounces, grams, grams_per_cup, unit_type, avg_weight_grams):
    db.execute(
        """UPDATE ingredient SET name=?, volume_amount=?, volume_unit=?, ounces=?,
           grams=?, grams_per_cup=?, unit_type=?, avg_weight_grams=?
           WHERE id=?""",
        (name, volume_amount, volume_unit, ounces, grams,
         grams_per_cup, unit_type, avg_weight_grams, ingredient_id),
    )
    db.commit()


# ── Recipe queries ─────────────────────────────────────────────────────────

def get_all_recipes(db):
    return db.execute("SELECT * FROM recipe ORDER BY id").fetchall()


def get_recipe_by_id(db, recipe_id):
    return db.execute("SELECT * FROM recipe WHERE id = ?", (recipe_id,)).fetchone()


def get_recipe_steps(db, recipe_id):
    return db.execute(
        "SELECT * FROM recipe_step WHERE recipe_id = ? ORDER BY step_number",
        (recipe_id,),
    ).fetchall()


def get_recipe_ingredients(db, recipe_id):
    return db.execute(
        """SELECT ri.*, i.grams_per_cup, i.unit_type, i.avg_weight_grams
           FROM recipe_ingredient ri
           LEFT JOIN ingredient i ON ri.ingredient_id = i.id
           WHERE ri.recipe_id = ?
           ORDER BY ri.sort_order""",
        (recipe_id,),
    ).fetchall()


# ── Recipe CRUD ───────────────────────────────────────────────────────────

def insert_recipe(db, title, image_path, servings, tags, source_url):
    cursor = db.execute(
        "INSERT INTO recipe (title, image_path, servings, tags, source_url) VALUES (?, ?, ?, ?, ?)",
        (title, image_path, servings, tags, source_url),
    )
    db.commit()
    return cursor.lastrowid


def update_recipe(db, recipe_id, title, image_path, servings, tags, source_url):
    db.execute(
        "UPDATE recipe SET title=?, image_path=?, servings=?, tags=?, source_url=? WHERE id=?",
        (title, image_path, servings, tags, source_url, recipe_id),
    )
    db.commit()


def delete_recipe(db, recipe_id):
    db.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
    db.execute("DELETE FROM recipe_step WHERE recipe_id = ?", (recipe_id,))
    db.execute("DELETE FROM recipe WHERE id = ?", (recipe_id,))
    db.commit()


def replace_recipe_steps(db, recipe_id, steps_list):
    db.execute("DELETE FROM recipe_step WHERE recipe_id = ?", (recipe_id,))
    for i, step in enumerate(steps_list, 1):
        db.execute(
            "INSERT INTO recipe_step (recipe_id, step_number, instruction) VALUES (?, ?, ?)",
            (recipe_id, i, step),
        )
    db.commit()


def replace_recipe_ingredients(db, recipe_id, ingredients_list):
    db.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
    for i, ing in enumerate(ingredients_list):
        row = get_ingredient_by_name(db, ing["name"])
        ingredient_id = row["id"] if row else None
        db.execute(
            """INSERT INTO recipe_ingredient
               (recipe_id, ingredient_id, name, amount, unit, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (recipe_id, ingredient_id, ing["name"], ing["amount"], ing["unit"], i),
        )
    db.commit()


# ── Recipe seeding ─────────────────────────────────────────────────────────

def seed_recipes(db):
    count = db.execute("SELECT COUNT(*) FROM recipe").fetchone()[0]
    if count > 0:
        return

    with open(RECIPES_PATH) as f:
        recipes = json.load(f)

    for r in recipes:
        cursor = db.execute(
            "INSERT INTO recipe (title, image_path, servings, tags) VALUES (?, ?, ?, ?)",
            (r["title"], r.get("image", ""), r["servings"], ",".join(r["tags"])),
        )
        recipe_id = cursor.lastrowid

        for i, step in enumerate(r["steps"], 1):
            db.execute(
                "INSERT INTO recipe_step (recipe_id, step_number, instruction) VALUES (?, ?, ?)",
                (recipe_id, i, step),
            )

        for i, ing in enumerate(r["ingredients"]):
            # Try to link to existing ingredient
            row = get_ingredient_by_name(db, ing["name"])
            ingredient_id = row["id"] if row else None
            db.execute(
                """INSERT INTO recipe_ingredient
                   (recipe_id, ingredient_id, name, amount, unit, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (recipe_id, ingredient_id, ing["name"], ing["amount"], ing["unit"], i),
            )

    db.commit()
