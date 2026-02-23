"""Our Kitchen — Flask recipe application."""

import hmac
import os
import time
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename

from database import (
    get_db, init_db, seed_recipes,
    get_all_recipes, get_recipe_by_id, get_recipe_steps, get_recipe_ingredients,
    get_all_ingredients, get_ingredient_by_name, insert_ingredient, update_ingredient,
    insert_recipe, update_recipe, delete_recipe,
    replace_recipe_steps, replace_recipe_ingredients,
)
try:
    from seed_king_arthur import seed as seed_ingredients
except ImportError:
    seed_ingredients = None
from conversions import format_amount, to_weight, normalize_to_grams_per_cup

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")


def admin_required(f):
    """Decorator that redirects to login if not authenticated as admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in to perform this action.", "error")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


@app.before_request
def ensure_db():
    """Initialize DB and seed on first request."""
    if not hasattr(app, "_db_initialized"):
        init_db()
        db = get_db()
        seed_recipes(db)
        db.close()
        if seed_ingredients:
            try:
                seed_ingredients()
            except Exception as e:
                app.logger.warning(f"Ingredient seeding skipped: {e}")
        app._db_initialized = True


# ── Template helpers ───────────────────────────────────────────────────

@app.template_filter("format_amount")
def format_amount_filter(n):
    return format_amount(n)


@app.context_processor
def utility_processor():
    return {"format_amount": format_amount, "is_admin": session.get("admin", False)}


# ── Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def home():
    db = get_db()
    recipes = get_all_recipes(db)
    db.close()
    return render_template("home.html", recipes=recipes)


@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    db = get_db()
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        db.close()
        return "Recipe not found", 404
    steps = get_recipe_steps(db, recipe_id)
    ingredients = get_recipe_ingredients(db, recipe_id)
    db.close()
    return render_template("recipe_detail.html",
                           recipe=recipe, steps=steps, ingredients=ingredients)


@app.route("/api/ingredients/search")
def api_ingredients_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    db = get_db()
    results = db.execute(
        "SELECT name FROM ingredient WHERE name LIKE ? COLLATE NOCASE ORDER BY name LIMIT 10",
        (f"%{q}%",),
    ).fetchall()
    db.close()
    return jsonify([r["name"] for r in results])


@app.route("/api/recipe/<int:recipe_id>/ingredients")
def api_recipe_ingredients(recipe_id):
    unit = request.args.get("unit", "volume")
    db = get_db()
    ingredients = get_recipe_ingredients(db, recipe_id)
    db.close()

    result = []
    for ing in ingredients:
        item = {
            "name": ing["name"],
            "amount": ing["amount"],
            "unit": ing["unit"],
        }
        if unit == "weight" and ing["grams_per_cup"]:
            grams = to_weight(ing["amount"], ing["unit"], ing["grams_per_cup"])
            if grams is not None:
                item["display"] = f"{grams} g"
            else:
                item["display"] = f"{format_amount(ing['amount'])} {ing['unit']}"
        else:
            item["display"] = f"{format_amount(ing['amount'])} {ing['unit']}"
        result.append(item)

    return jsonify(result)


@app.route("/api/shopping-list", methods=["POST"])
def api_shopping_list():
    data = request.get_json()
    plan = data.get("plan", {})
    unit_mode = data.get("unit", "volume")

    db = get_db()
    merged = {}

    for recipe_id_str, qty in plan.items():
        if qty <= 0:
            continue
        recipe_id = int(recipe_id_str)
        ingredients = get_recipe_ingredients(db, recipe_id)
        for ing in ingredients:
            key = ing["name"].lower()
            if key not in merged:
                merged[key] = {
                    "name": ing["name"],
                    "amount": 0,
                    "unit": ing["unit"],
                    "grams_per_cup": ing["grams_per_cup"],
                    "unit_type": ing["unit_type"],
                    "avg_weight_grams": ing["avg_weight_grams"],
                }
            merged[key]["amount"] += ing["amount"] * qty

    db.close()

    items = []
    for item in sorted(merged.values(), key=lambda x: x["name"].lower()):
        if unit_mode == "weight":
            if item["unit_type"] == "count" and item["avg_weight_grams"]:
                display = f"{round(item['amount'] * item['avg_weight_grams'])} g"
            elif item["grams_per_cup"]:
                grams = to_weight(item["amount"], item["unit"], item["grams_per_cup"])
                if grams is not None:
                    display = f"{grams} g"
                else:
                    display = f"{format_amount(item['amount'])} {item['unit']}"
            else:
                display = f"{format_amount(item['amount'])} {item['unit']}"
        else:
            display = f"{format_amount(item['amount'])} {item['unit']}"

        items.append({"name": item["name"], "display": display})

    return jsonify({"items": items})


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_image(file, recipe_id):
    """Save uploaded image and return the relative path for storage."""
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{recipe_id}_{int(time.time())}.{ext}"
    filepath = os.path.join(app.static_folder, "images", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file.save(filepath)
    return f"static/images/{filename}"


def _parse_recipe_form():
    """Extract recipe fields from the submitted form."""
    title = request.form.get("title", "").strip()
    servings = int(request.form.get("servings") or 4)
    tags = request.form.get("tags", "").strip()
    source_url = request.form.get("source_url", "").strip() or None
    instructions_text = request.form.get("instructions", "").strip()
    instructions_text = instructions_text.replace("\r\n", "\n").replace("\r", "\n")
    steps = [s.strip() for s in instructions_text.split("\n\n") if s.strip()]

    names = request.form.getlist("ing_name[]")
    amounts = request.form.getlist("ing_amount[]")
    units = request.form.getlist("ing_unit[]")
    ingredients = []
    for name, amount, unit in zip(names, amounts, units):
        name = name.strip()
        if not name:
            continue
        try:
            amt = float(amount) if amount else 0
        except ValueError:
            amt = 0
        ingredients.append({"name": name, "amount": amt, "unit": unit})

    return title, servings, tags, source_url, steps, ingredients


@app.route("/recipe/new", methods=["GET", "POST"])
@admin_required
def recipe_new():
    if request.method == "POST":
        title, servings, tags, source_url, steps, ingredients = _parse_recipe_form()
        if not title:
            flash("Title is required.", "error")
            return redirect(url_for("recipe_new"))

        db = get_db()
        image_path = ""
        file = request.files.get("image")
        # Insert first to get recipe_id, then save image
        recipe_id = insert_recipe(db, title, image_path, servings, tags, source_url)
        if file and file.filename and _allowed_file(file.filename):
            image_path = _save_image(file, recipe_id)
            update_recipe(db, recipe_id, title, image_path, servings, tags, source_url)
        replace_recipe_steps(db, recipe_id, steps)
        replace_recipe_ingredients(db, recipe_id, ingredients)
        db.close()
        flash(f"Created '{title}'.", "success")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    return render_template("recipe_form.html", recipe=None, steps_text="", ingredients=[])


@app.route("/recipe/<int:recipe_id>/edit", methods=["GET", "POST"])
@admin_required
def recipe_edit(recipe_id):
    db = get_db()
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        db.close()
        return "Recipe not found", 404

    if request.method == "POST":
        title, servings, tags, source_url, steps, ingredients = _parse_recipe_form()
        if not title:
            flash("Title is required.", "error")
            db.close()
            return redirect(url_for("recipe_edit", recipe_id=recipe_id))

        image_path = recipe["image_path"] or ""
        file = request.files.get("image")
        if file and file.filename and _allowed_file(file.filename):
            image_path = _save_image(file, recipe_id)

        update_recipe(db, recipe_id, title, image_path, servings, tags, source_url)
        replace_recipe_steps(db, recipe_id, steps)
        replace_recipe_ingredients(db, recipe_id, ingredients)
        db.close()
        flash(f"Updated '{title}'.", "success")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    steps = get_recipe_steps(db, recipe_id)
    ingredients = get_recipe_ingredients(db, recipe_id)
    steps_text = "\n\n".join(s["instruction"] for s in steps)
    db.close()
    return render_template("recipe_form.html", recipe=recipe, steps_text=steps_text,
                           ingredients=ingredients)


@app.route("/recipe/<int:recipe_id>/delete", methods=["POST"])
@admin_required
def recipe_delete(recipe_id):
    db = get_db()
    recipe = get_recipe_by_id(db, recipe_id)
    if not recipe:
        db.close()
        return "Recipe not found", 404
    delete_recipe(db, recipe_id)
    db.close()
    flash(f"Deleted '{recipe['title']}'.", "success")
    return redirect(url_for("home"))


# ── Auth ───────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if hmac.compare_digest(password, ADMIN_PASSWORD):
            session["admin"] = True
            flash("Logged in.", "success")
            next_url = request.args.get("next") or url_for("ingredients_page")
            return redirect(next_url)
        flash("Incorrect password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("Logged out.", "success")
    return redirect(url_for("home"))


# ── Ingredient management ──────────────────────────────────────────────

@app.route("/ingredients", methods=["GET", "POST"])
def ingredients_page():
    db = get_db()

    if request.method == "POST":
        if not session.get("admin"):
            flash("Please log in to perform this action.", "error")
            return redirect(url_for("login"))

        name = request.form.get("name", "").strip()
        unit_type = request.form.get("unit_type", "volume")

        if not name:
            flash("Name is required.", "error")
            return redirect(url_for("ingredients_page"))

        existing = get_ingredient_by_name(db, name)
        if existing:
            flash(f"Ingredient '{name}' already exists.", "error")
            db.close()
            return redirect(url_for("ingredients_page"))

        volume_amount = _parse_float(request.form.get("volume_amount"))
        volume_unit = request.form.get("volume_unit", "cup")
        ounces = _parse_float(request.form.get("ounces"))
        grams = _parse_float(request.form.get("grams"))
        avg_weight = _parse_float(request.form.get("avg_weight_grams"))

        grams_per_cup = None
        if volume_amount and volume_unit and grams:
            grams_per_cup = normalize_to_grams_per_cup(volume_amount, volume_unit, grams)

        insert_ingredient(db, name, volume_amount, volume_unit, ounces, grams,
                          grams_per_cup, unit_type, avg_weight)
        flash(f"Added '{name}'.", "success")
        db.close()
        return redirect(url_for("ingredients_page"))

    ingredients = get_all_ingredients(db)
    db.close()
    return render_template("ingredients.html", ingredients=ingredients)


@app.route("/ingredients/<int:ingredient_id>/edit", methods=["POST"])
@admin_required
def edit_ingredient(ingredient_id):
    db = get_db()
    name = request.form.get("name", "").strip()
    unit_type = request.form.get("unit_type", "volume")

    if not name:
        flash("Name is required.", "error")
        db.close()
        return redirect(url_for("ingredients_page"))

    volume_amount = _parse_float(request.form.get("volume_amount"))
    volume_unit = request.form.get("volume_unit", "cup")
    ounces = _parse_float(request.form.get("ounces"))
    grams = _parse_float(request.form.get("grams"))
    avg_weight = _parse_float(request.form.get("avg_weight_grams"))

    grams_per_cup = None
    if volume_amount and volume_unit and grams:
        grams_per_cup = normalize_to_grams_per_cup(volume_amount, volume_unit, grams)

    update_ingredient(db, ingredient_id, name, volume_amount, volume_unit,
                      ounces, grams, grams_per_cup, unit_type, avg_weight)
    flash(f"Updated '{name}'.", "success")
    db.close()
    return redirect(url_for("ingredients_page"))


def _parse_float(val):
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


if __name__ == "__main__":
    app.run(debug=True)
