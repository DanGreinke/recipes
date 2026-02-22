/* ── Our Kitchen — Client-side JS ────────────────────────────────────── */

(function () {
  "use strict";

  // ── Volume conversion constants ──────────────────────────────────────
  const TO_CUPS = {
    cup: 1, cups: 1,
    tbsp: 1 / 16, tablespoon: 1 / 16, tablespoons: 1 / 16,
    tsp: 1 / 48, teaspoon: 1 / 48, teaspoons: 1 / 48,
  };

  const DISPLAY_FRACTIONS = [
    [0.125, "⅛"], [0.25, "¼"], [1 / 3, "⅓"], [0.375, "⅜"],
    [0.5, "½"], [0.625, "⅝"], [2 / 3, "⅔"], [0.75, "¾"], [0.875, "⅞"],
  ];

  function formatAmt(n) {
    if (n == null || isNaN(n)) return "";
    if (n === Math.floor(n)) return String(n);
    var base = Math.floor(n);
    var frac = n - base;
    for (var i = 0; i < DISPLAY_FRACTIONS.length; i++) {
      if (Math.abs(frac - DISPLAY_FRACTIONS[i][0]) < 0.05) {
        return base ? base + " " + DISPLAY_FRACTIONS[i][1] : DISPLAY_FRACTIONS[i][1];
      }
    }
    return n % 1 === 0 ? String(n) : n.toFixed(1);
  }

  function toWeight(amount, unit, gramsPerCup) {
    if (!amount || !gramsPerCup) return null;
    var factor = TO_CUPS[unit.toLowerCase()];
    if (factor == null) return null;
    return Math.round(amount * factor * gramsPerCup);
  }

  // ── Recipe detail: unit toggle ───────────────────────────────────────
  var detailToggle = document.getElementById("detail-unit-toggle");
  if (detailToggle) {
    detailToggle.addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (!btn) return;
      detailToggle.querySelectorAll("button").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      var useWeight = btn.dataset.unit === "weight";
      updateIngredientDisplay(useWeight);
    });
  }

  function updateIngredientDisplay(useWeight) {
    var rows = document.querySelectorAll("#ingredient-list .ingredient-row");
    rows.forEach(function (row) {
      var amount = parseFloat(row.dataset.amount);
      var unit = row.dataset.unit;
      var gpc = parseFloat(row.dataset.gramsPerCup);
      var unitType = row.dataset.unitType;
      var avgWeight = parseFloat(row.dataset.avgWeight);
      var amountEl = row.querySelector(".ingredient-amount");

      if (useWeight) {
        if (unitType === "count" && avgWeight) {
          amountEl.textContent = Math.round(amount * avgWeight) + " g";
        } else if (gpc) {
          var grams = toWeight(amount, unit, gpc);
          if (grams != null) {
            amountEl.textContent = grams + " g";
          }
        }
      } else {
        amountEl.textContent = formatAmt(amount) + " " + unit;
      }
    });
  }

  // ── Home page: mode toggle + meal plan ───────────────────────────────
  var modeToggle = document.querySelector(".mode-toggle");
  if (!modeToggle) return;

  var mode = "browse";
  var plan = {}; // { recipeId: qty }
  var recipeGrid = document.getElementById("recipe-grid");
  var planBanner = document.getElementById("plan-banner");
  var planBar = document.getElementById("plan-bar");
  var planBarItems = document.getElementById("plan-bar-items");
  var generateBtn = document.getElementById("generate-list-btn");
  var shoppingView = document.getElementById("shopping-list-view");
  var homeView = document.getElementById("home-view");
  var backToSelection = document.getElementById("back-to-selection");
  var shoppingUnitToggle = document.getElementById("shopping-unit-toggle");
  var shoppingListContent = document.getElementById("shopping-list-content");
  var shoppingSubtitle = document.getElementById("shopping-list-subtitle");

  // Mode toggle buttons
  modeToggle.addEventListener("click", function (e) {
    var btn = e.target.closest("button");
    if (!btn) return;
    var newMode = btn.dataset.mode;
    if (newMode === mode) return;
    mode = newMode;
    modeToggle.querySelectorAll("button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.mode === mode);
    });
    updateView();
  });

  function updateView() {
    if (mode === "plan") {
      planBanner.style.display = "flex";
      recipeGrid.classList.add("plan-mode");
    } else {
      planBanner.style.display = "none";
      recipeGrid.classList.remove("plan-mode");
    }
    showShoppingList(false);
    updateCards();
    updatePlanBar();
  }

  // Card clicks
  recipeGrid.addEventListener("click", function (e) {
    if (mode !== "plan") return;
    var card = e.target.closest(".recipe-card[data-recipe-id]");
    if (!card) return;
    e.preventDefault();
    var id = card.dataset.recipeId;
    plan[id] = plan[id] ? 0 : 1;
    updateCards();
    updatePlanBar();
  });

  function updateCards() {
    var cards = recipeGrid.querySelectorAll(".recipe-card[data-recipe-id]");
    cards.forEach(function (card) {
      var id = card.dataset.recipeId;
      var qty = plan[id] || 0;
      var badge = card.querySelector(".badge");
      if (qty > 0 && mode === "plan") {
        card.classList.add("in-plan");
        if (badge) { badge.style.display = "flex"; badge.textContent = qty; }
      } else {
        card.classList.remove("in-plan");
        if (badge) badge.style.display = "none";
      }

      // In plan mode, prevent link navigation
      var link = card.querySelector(".card-link");
      if (link) {
        if (mode === "plan") {
          link.style.pointerEvents = "none";
        } else {
          link.style.pointerEvents = "";
        }
      }
    });
  }

  function updatePlanBar() {
    var total = Object.values(plan).reduce(function (a, b) { return a + b; }, 0);
    if (total > 0 && mode === "plan") {
      planBar.classList.add("visible");
    } else {
      planBar.classList.remove("visible");
    }

    planBarItems.innerHTML = "";
    Object.keys(plan).forEach(function (id) {
      var qty = plan[id];
      if (qty <= 0) return;
      var card = recipeGrid.querySelector('[data-recipe-id="' + id + '"]');
      if (!card) return;
      var title = card.dataset.title;
      var emoji = card.dataset.image;

      var item = document.createElement("div");
      item.className = "plan-bar-item";
      item.innerHTML =
        '<span class="plan-bar-item-emoji">' + emoji + '</span>' +
        '<span class="plan-bar-item-title">' + title + '</span>' +
        '<button class="qty-btn" data-id="' + id + '" data-delta="-1">&minus;</button>' +
        '<span class="qty-value">' + qty + '</span>' +
        '<button class="qty-btn" data-id="' + id + '" data-delta="1">+</button>';
      planBarItems.appendChild(item);
    });
  }

  // Qty adjust in plan bar
  planBar.addEventListener("click", function (e) {
    var btn = e.target.closest(".qty-btn");
    if (!btn) return;
    var id = btn.dataset.id;
    var delta = parseInt(btn.dataset.delta);
    plan[id] = Math.max(0, (plan[id] || 0) + delta);
    updateCards();
    updatePlanBar();
  });

  // Generate shopping list
  generateBtn.addEventListener("click", function () {
    var total = Object.values(plan).reduce(function (a, b) { return a + b; }, 0);
    if (total === 0) return;
    fetchShoppingList("volume");
  });

  function fetchShoppingList(unitMode) {
    fetch("/api/shopping-list", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan: plan, unit: unitMode }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        renderShoppingList(data);
        showShoppingList(true);
      });
  }

  function showShoppingList(show) {
    if (show) {
      recipeGrid.style.display = "none";
      planBanner.style.display = "none";
      planBar.classList.remove("visible");
      shoppingView.style.display = "block";
      var total = Object.values(plan).reduce(function (a, b) { return a + b; }, 0);
      shoppingSubtitle.textContent = "Combined ingredients for " + total + " meal" + (total !== 1 ? "s" : "");
    } else {
      recipeGrid.style.display = "";
      shoppingView.style.display = "none";
      if (mode === "plan") {
        var t = Object.values(plan).reduce(function (a, b) { return a + b; }, 0);
        if (t > 0) planBar.classList.add("visible");
        planBanner.style.display = "flex";
      }
    }
  }

  backToSelection.addEventListener("click", function (e) {
    e.preventDefault();
    showShoppingList(false);
  });

  // Shopping list unit toggle
  shoppingUnitToggle.addEventListener("click", function (e) {
    var btn = e.target.closest("button");
    if (!btn) return;
    shoppingUnitToggle.querySelectorAll("button").forEach(function (b) {
      b.classList.remove("active");
    });
    btn.classList.add("active");
    fetchShoppingList(btn.dataset.unit);
  });

  function renderShoppingList(data) {
    var items = data.items;
    if (!items || items.length === 0) {
      shoppingListContent.innerHTML =
        '<div class="empty-state"><div class="empty-state-icon">&#x1F6D2;</div>Select recipes above to generate your shopping list</div>';
      return;
    }

    var recipeCount = Object.values(plan).filter(function (v) { return v > 0; }).length;
    var html = '<div class="list-section">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">';
    html += '<div class="section-title">Shopping List</div>';
    html += '</div>';

    items.forEach(function (item) {
      html += '<div class="list-item">';
      html += '<span class="list-item-name">' + item.name + '</span>';
      html += '<span class="list-item-amount">' + item.display + '</span>';
      html += '</div>';
    });

    html += '<div class="list-footer">' + items.length + ' items &bull; Quantities combined across ' + recipeCount + ' recipe(s)</div>';
    html += '</div>';
    shoppingListContent.innerHTML = html;
  }
})();
