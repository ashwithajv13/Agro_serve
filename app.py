# app.py - AGRO SERVE
# Flask connects URLs (routes) to HTML templates. Crop data and the scoring rules live here.
import re
from flask import Flask, render_template, request, session, redirect, url_for, abort

app = Flask(__name__)
app.secret_key = "change-this-before-deploying"   # needed for the session (dashboard history)

SOILS = ["Black Soil", "Red Soil", "Sandy Soil", "Clay Soil", "Alluvial Soil", "Loamy Soil"]
SEASONS = ["Kharif", "Rabi", "Zaid"]
WATER_LEVELS = ["Low", "Moderate", "High"]

def make_crop(name, icon, c1, c2, desc, soils, seasons, water, rain, duration, tips,
              yield_q, price, cost, nutrients):
    """Builds one crop record. yield_q = quintals/acre, price = Rs/quintal, cost = Rs/acre.
    NOTE: price, yield and cost are SAMPLE values for demonstration, not live market data."""
    return dict(name=name, slug=name.lower(), icon=icon, c1=c1, c2=c2, desc=desc, soils=soils,
                seasons=seasons, water=water, rain=rain, duration=duration, tips=tips,
                yield_q=yield_q, price=price, cost=cost, nutrients=nutrients)

CROPS = [
    make_crop("Rice", "🌾", "#bfe3a0", "#6fb26a", "India's staple grain, grown in flooded fields.",
              ["Clay Soil", "Alluvial Soil"], ["Kharif"], "High", (1000, 1500), "120-150 days",
              ["Level the field and keep a thin layer of water.", "Transplant healthy seedlings 20-25 days old.", "Drain the field a week before harvest."],
              22, 2300, 28000, "High nitrogen, moderate phosphorus and potash. Urea, DAP, MOP; split nitrogen into 2-3 doses."),
    make_crop("Wheat", "🌾", "#f6dc8c", "#d9a441", "A cool-season cereal that thrives in winter.",
              ["Loamy Soil", "Alluvial Soil"], ["Rabi"], "Moderate", (400, 800), "110-130 days",
              ["Sow in November for best yield.", "Irrigate at crown root and flowering stages.", "Remove weeds in the first 40 days."],
              18, 2425, 20000, "Balanced N-P-K. Apply phosphorus and potash at sowing, nitrogen in two splits."),
    make_crop("Maize", "🌽", "#fbe38a", "#e3b23c", "A fast-growing, versatile cereal for food and fodder.",
              ["Loamy Soil", "Red Soil"], ["Kharif", "Rabi"], "Moderate", (600, 1100), "90-110 days",
              ["Ensure good drainage; waterlogging harms roots.", "Earth up plants at 30-35 days.", "Water at tasseling and grain filling."],
              24, 2090, 18000, "Responds well to nitrogen. Urea in splits, DAP at sowing, add zinc if deficient."),
    make_crop("Cotton", "☁️", "#e9eef2", "#aebdc9", "A cash crop grown for fibre, best on black soil.",
              ["Black Soil"], ["Kharif"], "Moderate", (600, 1000), "150-180 days",
              ["Keep proper plant spacing for airflow.", "Scout regularly for bollworm.", "Pick bolls when fully open and dry."],
              8, 7000, 32000, "Needs nitrogen and potash. Apply in splits; avoid excess nitrogen."),
    make_crop("Sugarcane", "🎋", "#c8e8a8", "#7fbf6a", "A long-duration, high-water crop grown for sugar.",
              ["Loamy Soil", "Black Soil"], ["Kharif", "Rabi", "Zaid"], "High", (1100, 1500), "10-12 months",
              ["Plant disease-free setts.", "Irrigate regularly, especially in summer.", "Trash mulching saves water."],
              350, 340, 70000, "Heavy feeder of nitrogen and potash. Apply in 3 splits with organic manure."),
    make_crop("Groundnut", "🥜", "#f1cfa0", "#c98f55", "A hardy oilseed that suits light, well-drained soil.",
              ["Sandy Soil", "Red Soil"], ["Kharif", "Zaid"], "Low", (500, 900), "100-120 days",
              ["Prefer loose soil so pods can form.", "Apply gypsum at flowering.", "Avoid standing water."],
              9, 6300, 25000, "Needs phosphorus, calcium and sulphur. Gypsum at flowering; little nitrogen."),
    make_crop("Ragi", "🌱", "#e6c3a8", "#b9785a", "A nutritious millet that tolerates dry conditions.",
              ["Red Soil", "Sandy Soil"], ["Kharif"], "Low", (500, 900), "100-120 days",
              ["Transplant seedlings for higher yield.", "Needs little irrigation once established.", "Thin and weed at 20-25 days."],
              9, 4290, 14000, "Moderate nitrogen and phosphorus. Farmyard manure improves yield."),
    make_crop("Jowar", "🌿", "#d8e6a0", "#9bb84a", "Sorghum: a drought-tolerant grain and fodder crop.",
              ["Black Soil", "Red Soil"], ["Kharif", "Rabi"], "Low", (450, 800), "100-110 days",
              ["Sow at the start of the rains.", "Thin plants to the right spacing.", "Harvest when grains harden."],
              8, 3180, 12000, "Moderate nitrogen. Apply half at sowing and half at 30 days."),
    make_crop("Millets", "🌾", "#f3e1a6", "#cfae52", "Hardy small-grain crops that need very little water.",
              ["Sandy Soil", "Red Soil"], ["Kharif"], "Low", (350, 700), "70-90 days",
              ["Suits poor, dry soils.", "Sow with the first good rain.", "Very low input cost."],
              10, 2625, 11000, "Low nutrient needs. A small dose of nitrogen and farmyard manure is enough."),
]
CROPS_BY_SLUG = {c["slug"]: c for c in CROPS}

# ---------- Scoring rules (simple and explainable) ----------
# Soil 30 + Season 30 + Rainfall 20 + Water 20 = 100 points
def score_crop(crop, soil, season, rainfall, water):
    score, reasons = 0, []
    if soil in crop["soils"]:
        score += 30; reasons.append(f"{soil} suits {crop['name']}.")
    else:
        reasons.append(f"{soil} is not the best soil for {crop['name']}.")
    if season in crop["seasons"]:
        score += 30; reasons.append(f"{season} is a good growing season for it.")
    else:
        reasons.append(f"It is usually grown in {', '.join(crop['seasons'])}, not {season}.")
    low, high = crop["rain"]
    if low <= rainfall <= high:
        score += 20; reasons.append(f"Your rainfall ({rainfall} mm) is within its ideal {low}-{high} mm range.")
    else:
        gap = low - rainfall if rainfall < low else rainfall - high
        score += max(0, 20 - gap / 25)      # lose 1 point per 25 mm outside the range
        reasons.append(f"Your rainfall ({rainfall} mm) is outside its ideal {low}-{high} mm range.")
    step = abs(WATER_LEVELS.index(crop["water"]) - WATER_LEVELS.index(water))
    score += [20, 10, 0][step]
    reasons.append(f"It needs {crop['water'].lower()} water; you have {water.lower()}.")
    return round(score), reasons

def category(score):
    return "Highly Suitable" if score >= 80 else "Suitable" if score >= 50 else "Less Suitable"

# ---------- Profit formulas ----------
def estimate_profit(crop, acres):
    total_yield = crop["yield_q"] * acres                 # quintals
    income = total_yield * crop["price"]                  # Rs
    cost = crop["cost"] * acres                           # Rs
    return dict(crop=crop, total_yield=total_yield, income=income, cost=cost, profit=income - cost)

@app.template_filter("inr")
def inr(value):
    """Formats a number the Indian way: 1,25,000"""
    n = int(round(value)); sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
    return f"{sign}₹{s}"

# ---------- Routes ----------
@app.route("/")
def home():
    popular = [CROPS_BY_SLUG[s] for s in ["rice", "wheat", "maize", "cotton", "groundnut", "ragi"]]
    return render_template("index.html", popular=popular)

@app.route("/farm-details")
def farm_details():
    return render_template("farm_details.html", soils=SOILS, seasons=SEASONS, levels=WATER_LEVELS, form={}, error=None)

@app.route("/recommendations", methods=["GET", "POST"])
def recommendations():
    if request.method == "GET":
        return redirect(url_for("farm_details"))
    form = request.form
    try:
        rainfall, acres = float(form["rainfall"]), float(form["acres"])
        soil, season, water = form["soil"], form["season"], form["water"]
        assert soil in SOILS and season in SEASONS and water in WATER_LEVELS
        assert 100 <= rainfall <= 4000 and 0.1 <= acres <= 1000
    except (KeyError, ValueError, AssertionError):
        return render_template("farm_details.html", soils=SOILS, seasons=SEASONS, levels=WATER_LEVELS, form=form,
                               error="Please check your entries: rainfall must be 100-4000 mm and land area 0.1-1000 acres.")
    results = []
    for crop in CROPS:
        score, reasons = score_crop(crop, soil, season, rainfall, water)
        results.append(dict(crop=crop, score=score, label=category(score), reasons=reasons))
    results.sort(key=lambda r: r["score"], reverse=True)
    top = results[:6]
    # Remember this search for the dashboard (stored in the browser's session cookie)
    history = session.get("history", [])
    history.insert(0, dict(name=form.get("name", "").strip() or "Farmer", district=form.get("district", "").strip(),
                           soil=soil, season=season, rainfall=int(rainfall), water=water, acres=acres,
                           best=top[0]["crop"]["name"], score=top[0]["score"]))
    session["history"] = history[:6]
    summary = dict(name=form.get("name", "").strip() or "Farmer", district=form.get("district", "").strip(),
                   soil=soil, season=season, rainfall=int(rainfall), water=water, acres=acres)
    return render_template("recommendations.html", results=top, summary=summary)

@app.route("/crops")
def crop_info():
    return render_template("crop_info.html", crops=CROPS)

@app.route("/crops/<slug>")
def crop_detail(slug):
    crop = CROPS_BY_SLUG.get(slug) or abort(404)
    return render_template("crop_detail.html", crop=crop)

@app.route("/compare")
def compare():
    picks = [CROPS_BY_SLUG[s] for s in [request.args.get(k) for k in "abc"] if s in CROPS_BY_SLUG]
    if not picks:
        picks = [CROPS_BY_SLUG[s] for s in ["rice", "cotton", "groundnut"]]
    try:
        acres = min(max(float(request.args.get("acres", 5)), 0.1), 1000)
    except ValueError:
        acres = 5
    rows = [estimate_profit(c, acres) for c in picks]
    best = max(r["profit"] for r in rows)
    return render_template("compare.html", crops=CROPS, rows=rows, acres=acres, best=best,
                           selected=[c["slug"] for c in picks])

@app.route("/farming-guide")
def farming_guide():
    return render_template("farming_guide.html", crops=CROPS)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        session.pop("history", None)
        return redirect(url_for("dashboard"))
    return render_template("dashboard.html", history=session.get("history", []))

@app.route("/about", methods=["GET", "POST"])
def about():
    sent = request.method == "POST"      # Step 9 will save messages in the database
    return render_template("about_contact.html", sent=sent, name=request.form.get("name", ""))

if __name__ == "__main__":
    app.run(debug=True)
