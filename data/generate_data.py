"""
Synthetic CPG data generator for the Trade Promotion ROI Optimizer.
Run: python data/generate_data.py
Generates all 7 CSV files in the data/ directory following the Data Dictionary v1.0.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
import os
import pathlib

SEED = 42
rng = np.random.default_rng(SEED)
OUTPUT_DIR = pathlib.Path(__file__).parent

# ── SKU catalog ──────────────────────────────────────────────────────────────

SKU_CATALOG = [
    # BrewCo – Coffee (10 SKUs)
    ("BrewCo", "Coffee", "Premium Ground", "Premium Coffee 250g",   "250g",  450.00, 220.00, "2022-01-03"),
    ("BrewCo", "Coffee", "Premium Ground", "Premium Coffee 500g",   "500g",  850.00, 400.00, "2022-01-03"),
    ("BrewCo", "Coffee", "Classic Ground", "Classic Coffee 250g",   "250g",  280.00, 135.00, "2022-01-03"),
    ("BrewCo", "Coffee", "Classic Ground", "Classic Coffee 500g",   "500g",  520.00, 250.00, "2022-01-03"),
    ("BrewCo", "Coffee", "Classic Ground", "Classic Coffee 1kg",    "1kg",   999.00, 475.00, "2022-01-03"),
    ("BrewCo", "Coffee", "Instant",        "Instant Coffee 50g",    "50g",   125.00,  55.00, "2022-04-01"),
    ("BrewCo", "Coffee", "Instant",        "Instant Coffee 100g",   "100g",  225.00,  98.00, "2022-04-01"),
    ("BrewCo", "Coffee", "Instant",        "Instant Coffee 200g",   "200g",  420.00, 185.00, "2022-04-01"),
    ("BrewCo", "Coffee", "Filter",         "Filter Coffee 250g",    "250g",  199.00,  90.00, "2022-06-01"),
    ("BrewCo", "Coffee", "Filter",         "Filter Coffee 500g",    "500g",  380.00, 170.00, "2022-06-01"),
    # SipWell – Tea (10 SKUs)
    ("SipWell", "Tea", "Green Tea",   "Green Tea 25 bags",    "25 bags", 185.00,  72.00, "2022-01-03"),
    ("SipWell", "Tea", "Green Tea",   "Green Tea 50 bags",    "50 bags", 349.00, 135.00, "2022-01-03"),
    ("SipWell", "Tea", "Green Tea",   "Green Tea 100 bags",   "100 bags",649.00, 248.00, "2022-01-03"),
    ("SipWell", "Tea", "Black Tea",   "Black Tea 100g",        "100g",   155.00,  60.00, "2022-01-03"),
    ("SipWell", "Tea", "Black Tea",   "Black Tea 250g",        "250g",   349.00, 135.00, "2022-01-03"),
    ("SipWell", "Tea", "Black Tea",   "Black Tea 500g",        "500g",   649.00, 248.00, "2022-01-03"),
    ("SipWell", "Tea", "Herbal Tea",  "Herbal Tea 20 bags",    "20 bags",220.00,  88.00, "2023-01-02"),
    ("SipWell", "Tea", "Herbal Tea",  "Herbal Tea 50 bags",    "50 bags",499.00, 192.00, "2023-01-02"),
    ("SipWell", "Tea", "Premium Tea", "Premium Tea 25 bags",   "25 bags",499.00, 188.00, "2022-06-01"),
    ("SipWell", "Tea", "Premium Tea", "Premium Tea 50 bags",   "50 bags",949.00, 355.00, "2022-06-01"),
    # SipWell – Juice (10 SKUs)
    ("SipWell", "Juice", "Mango",        "Mango Juice 200ml",    "200ml",  30.00,  18.00, "2022-01-03"),
    ("SipWell", "Juice", "Mango",        "Mango Juice 1L",        "1L",    120.00,  70.00, "2022-01-03"),
    ("SipWell", "Juice", "Mixed Fruit",  "Mixed Fruit 200ml",    "200ml",  28.00,  17.00, "2022-01-03"),
    ("SipWell", "Juice", "Mixed Fruit",  "Mixed Fruit 1L",        "1L",    110.00,  65.00, "2022-01-03"),
    ("SipWell", "Juice", "Citrus",       "Orange Juice 200ml",   "200ml",  25.00,  15.00, "2022-01-03"),
    ("SipWell", "Juice", "Citrus",       "Orange Juice 1L",       "1L",     99.00,  60.00, "2022-01-03"),
    ("SipWell", "Juice", "Citrus",       "Apple Juice 1L",        "1L",    135.00,  80.00, "2022-03-01"),
    ("SipWell", "Juice", "Coconut",      "Coconut Water 200ml",  "200ml",  40.00,  22.00, "2023-04-01"),
    ("SipWell", "Juice", "Coconut",      "Coconut Water 500ml",  "500ml",  90.00,  48.00, "2023-04-01"),
    ("SipWell", "Juice", "Coconut",      "Coconut Water 1L",      "1L",    165.00,  88.00, "2023-04-01"),
    # SnackRight – Chips (10 SKUs)
    ("SnackRight", "Chips", "Classic",    "Classic Chips 100g",   "100g",  40.00,  17.00, "2022-01-03"),
    ("SnackRight", "Chips", "Classic",    "Classic Chips 200g",   "200g",  75.00,  32.00, "2022-01-03"),
    ("SnackRight", "Chips", "Classic",    "Classic Chips 500g",   "500g", 175.00,  74.00, "2022-01-03"),
    ("SnackRight", "Chips", "Flavoured",  "Spicy Chips 100g",     "100g",  40.00,  17.00, "2022-01-03"),
    ("SnackRight", "Chips", "Flavoured",  "Cheese Chips 100g",    "100g",  45.00,  19.00, "2022-01-03"),
    ("SnackRight", "Chips", "Flavoured",  "Sour Cream Chips 100g","100g",  45.00,  19.00, "2022-06-01"),
    ("SnackRight", "Chips", "Premium",    "Premium Chips 125g",   "125g",  65.00,  26.00, "2022-06-01"),
    ("SnackRight", "Chips", "Premium",    "Premium Chips 250g",   "250g", 120.00,  48.00, "2022-06-01"),
    ("SnackRight", "Chips", "Premium",    "Multigrain Chips 100g","100g",  55.00,  24.00, "2023-01-02"),
    ("SnackRight", "Chips", "Premium",    "Baked Chips 150g",     "150g",  70.00,  35.00, "2023-06-01"),
    # SnackRight – Biscuits (10 SKUs)
    ("SnackRight", "Biscuits", "Plain",       "Classic Biscuit 100g",   "100g",  25.00,  11.00, "2022-01-03"),
    ("SnackRight", "Biscuits", "Plain",       "Classic Biscuit 250g",   "250g",  55.00,  24.00, "2022-01-03"),
    ("SnackRight", "Biscuits", "Plain",       "Classic Biscuit 500g",   "500g",  99.00,  43.00, "2022-01-03"),
    ("SnackRight", "Biscuits", "Chocolate",   "Choco Biscuit 100g",     "100g",  45.00,  20.00, "2022-01-03"),
    ("SnackRight", "Biscuits", "Chocolate",   "Choco Biscuit 250g",     "250g",  99.00,  43.00, "2022-01-03"),
    ("SnackRight", "Biscuits", "Chocolate",   "Choco Biscuit 500g",     "500g", 185.00,  80.00, "2022-01-03"),
    ("SnackRight", "Biscuits", "Health",      "Digestive 200g",         "200g",  75.00,  34.00, "2022-06-01"),
    ("SnackRight", "Biscuits", "Health",      "Digestive 400g",         "400g", 140.00,  63.00, "2022-06-01"),
    ("SnackRight", "Biscuits", "Health",      "Oat Biscuit 200g",       "200g",  95.00,  45.00, "2023-01-02"),
    ("SnackRight", "Biscuits", "Health",      "Protein Cookie 180g",    "180g", 149.00,  82.00, "2023-06-01"),
]

# ── Retailer catalog ──────────────────────────────────────────────────────────

RETAILER_CATALOG = [
    # Tier 1 (5)
    ("RET-001", "BigMart",        "Modern Trade",    "South", "Tier 1", 0.30, 12500),
    ("RET-002", "SuperShop",      "Modern Trade",    "West",  "Tier 1", 0.25, 11000),
    ("RET-003", "EcomGiant",      "E-commerce",      "North", "Tier 1", 0.20, 15000),
    ("RET-004", "MegaStore",      "Modern Trade",    "East",  "Tier 1", 0.30, 10500),
    ("RET-005", "FreshMart",      "E-commerce",      "South", "Tier 1", 0.20, 13500),
    # Tier 2 (10)
    ("RET-006", "ValueMart",      "Modern Trade",    "North", "Tier 2", 0.20,  6500),
    ("RET-007", "QuickShop",      "Modern Trade",    "South", "Tier 2", 0.18,  5800),
    ("RET-008", "DigiBazaar",     "E-commerce",      "West",  "Tier 2", 0.15,  7200),
    ("RET-009", "TownMart",       "Modern Trade",    "East",  "Tier 2", 0.22,  5200),
    ("RET-010", "NorthGrocers",   "Modern Trade",    "North", "Tier 2", 0.20,  4800),
    ("RET-011", "EastFresh",      "Modern Trade",    "East",  "Tier 2", 0.18,  5500),
    ("RET-012", "WestMall",       "Modern Trade",    "West",  "Tier 2", 0.22,  6000),
    ("RET-013", "CityGrocer",     "E-commerce",      "South", "Tier 2", 0.15,  6800),
    ("RET-014", "RegionalMart",   "Modern Trade",    "North", "Tier 2", 0.20,  5000),
    ("RET-015", "PremiumShop",    "Modern Trade",    "West",  "Tier 2", 0.25,  4500),
    # Tier 3 (5)
    ("RET-016", "KiranaMart",     "Traditional Trade","South","Tier 3", 0.05,  1200),
    ("RET-017", "NeighbourStore", "Traditional Trade","North","Tier 3", 0.05,   950),
    ("RET-018", "VillageShop",    "Traditional Trade","East", "Tier 3", 0.05,   800),
    ("RET-019", "LocalGrocer",    "Traditional Trade","West", "Tier 3", 0.05,  1100),
    ("RET-020", "CornorStore",    "Traditional Trade","South","Tier 3", 0.05,   900),
]

# ── Base elasticities and velocity by category ────────────────────────────────

CATEGORY_PARAMS = {
    "Coffee":   {"elasticity": 2.5, "base_vel": 180},
    "Tea":      {"elasticity": 2.0, "base_vel": 150},
    "Juice":    {"elasticity": 1.5, "base_vel": 350},
    "Chips":    {"elasticity": 2.0, "base_vel": 400},
    "Biscuits": {"elasticity": 1.8, "base_vel": 450},
}

MECHANIC_MULT = {
    "Price Off": 1.0,
    "BOGO":      1.8,
    "Display":   0.6,
    "Feature":   0.8,
    "Combo":     0.7,
}

SEASON_MULT = {
    "Winter":  1.10,
    "Summer":  0.90,
    "Monsoon": 0.95,
    "Festive": 1.25,
}

FESTIVAL_MULT = 1.40

# ── Calendar ──────────────────────────────────────────────────────────────────

FESTIVAL_DATES = {
    date(2024, 3, 25): "Holi",
    date(2024, 4, 10): "Eid",
    date(2024, 11,  1): "Diwali",
    date(2024, 12, 25): "Christmas",
    date(2024, 12, 30): "New Year",
    date(2025, 3, 14): "Holi",
    date(2025, 3, 31): "Eid",
    date(2025, 10, 20): "Diwali",
    date(2025, 12, 25): "Christmas",
    date(2025, 12, 29): "New Year",
}


def generate_calendar() -> pd.DataFrame:
    start = date(2024, 1, 1)
    rows = []
    for i in range(104):
        ws = start + timedelta(weeks=i)
        we = ws + timedelta(days=6)
        m = ws.month
        y = ws.year
        q = (m - 1) // 3 + 1
        if m in (12, 1, 2):
            season = "Winter"
        elif m in (3, 4, 5):
            season = "Summer"
        elif m in (6, 7, 8, 9):
            season = "Monsoon"
        else:
            season = "Festive"

        festival_flag = ""
        is_holiday = False
        for fd, fname in FESTIVAL_DATES.items():
            if ws <= fd <= we:
                festival_flag = fname
                is_holiday = True
                break

        rows.append({
            "week_id": ws.strftime("%Y-W%V"),
            "week_start_date": ws.isoformat(),
            "week_end_date": we.isoformat(),
            "month": m,
            "quarter": f"Q{q}-{y}",
            "fiscal_year": y,
            "season": season,
            "is_holiday_week": is_holiday,
            "festival_flag": festival_flag,
        })
    return pd.DataFrame(rows)


def generate_sku_master() -> pd.DataFrame:
    rows = []
    for i, (brand, cat, subcat, name, pack, price, cogs, launch) in enumerate(SKU_CATALOG, 1):
        margin = round((price - cogs) / price, 4)
        rows.append({
            "sku_id": f"SKU-{i:04d}",
            "sku_name": name,
            "brand": brand,
            "category": cat,
            "subcategory": subcat,
            "pack_size": pack,
            "list_price": price,
            "cogs_per_unit": cogs,
            "gross_margin_pct": margin,
            "launch_date": launch,
        })
    return pd.DataFrame(rows)


def generate_retailer_master() -> pd.DataFrame:
    rows = []
    for ret_id, name, channel, region, tier, coop, vol in RETAILER_CATALOG:
        rows.append({
            "retailer_id": ret_id,
            "retailer_name": name,
            "channel": channel,
            "region": region,
            "tier": tier,
            "coop_funding_pct": coop,
            "avg_weekly_volume_units": vol,
        })
    return pd.DataFrame(rows)


def generate_cannibalization_matrix(sku_master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    skus = sku_master.copy()
    pair_id = set()

    for _, a in skus.iterrows():
        for _, b in skus.iterrows():
            if a["sku_id"] == b["sku_id"]:
                continue
            pair = tuple(sorted([a["sku_id"], b["sku_id"]]))
            if pair in pair_id:
                continue
            if a["brand"] == b["brand"] and a["subcategory"] == b["subcategory"]:
                ce = round(float(rng.uniform(0.15, 0.30)), 3)
                rel = "Same brand"
            elif a["brand"] == b["brand"] and a["category"] == b["category"]:
                ce = round(float(rng.uniform(0.05, 0.14)), 3)
                rel = "Same brand"
            elif a["category"] == b["category"] and a["brand"] != b["brand"]:
                if rng.random() < 0.3:
                    ce = round(float(rng.uniform(0.03, 0.10)), 3)
                    rel = "Competing brand"
                else:
                    continue
            else:
                continue

            pair_id.add(pair)
            rows.append({"sku_a": a["sku_id"], "sku_b": b["sku_id"],
                         "cross_elasticity": ce, "relationship_type": rel})
            # non-symmetric reverse entry with slight variation
            rows.append({"sku_a": b["sku_id"], "sku_b": a["sku_id"],
                         "cross_elasticity": round(ce * float(rng.uniform(0.7, 1.0)), 3),
                         "relationship_type": rel})

    return pd.DataFrame(rows)


def _seasonal_mult(week_id: str, calendar: pd.DataFrame) -> float:
    row = calendar[calendar["week_id"] == week_id]
    if row.empty:
        return 1.0
    season = row.iloc[0]["season"]
    mult = SEASON_MULT.get(season, 1.0)
    if row.iloc[0]["festival_flag"]:
        mult *= FESTIVAL_MULT / SEASON_MULT.get(season, 1.0)  # override, not stack
    return mult


def generate_promo_history(
    sku_master: pd.DataFrame,
    retailer_master: pd.DataFrame,
    calendar: pd.DataFrame,
) -> pd.DataFrame:
    weeks = calendar["week_id"].tolist()
    mechanics = ["Price Off", "Price Off", "Price Off", "Display", "Feature", "BOGO", "Combo"]
    rows = []
    promo_num = 1

    skus = sku_master[sku_master["launch_date"] < "2024-01-01"].copy()
    retailers = retailer_master.copy()

    for _ in range(800):
        sku = skus.sample(1, random_state=int(rng.integers(0, 99999))).iloc[0]
        ret = retailers.sample(1, random_state=int(rng.integers(0, 99999))).iloc[0]
        mech = rng.choice(mechanics)
        start_idx = int(rng.integers(0, len(weeks) - 12))
        dur = 1 if mech == "Feature" else int(rng.integers(1, 5))
        if mech == "Display":
            dur = max(2, dur)  # at least 14 days = 2 weeks
        end_idx = min(start_idx + dur - 1, len(weeks) - 1)
        start_wk = weeks[start_idx]
        end_wk = weeks[end_idx]

        # Discount depth rules
        max_disc = 0.15 if sku["list_price"] > 400 else 0.30
        min_disc = 0.05
        disc = round(float(rng.uniform(min_disc, max_disc)), 3)

        # BOGO: only for margin > 40%
        if mech == "BOGO" and sku["gross_margin_pct"] <= 0.40:
            mech = "Price Off"

        # Lift estimate
        cat = sku["category"]
        elast = CATEGORY_PARAMS.get(cat, {"elasticity": 2.0})["elasticity"]
        base_vel = CATEGORY_PARAMS.get(cat, {"base_vel": 200})["base_vel"]
        tier_mult = {"Tier 1": 1.5, "Tier 2": 0.8, "Tier 3": 0.25}[ret["tier"]]
        s_mult = _seasonal_mult(start_wk, calendar)
        lift = elast * disc * MECHANIC_MULT[mech] * s_mult
        noise = float(rng.normal(1.0, 0.10))
        base_units_week = max(10, int(base_vel * tier_mult))
        planned_units = int(base_units_week * (dur + 1) * (1 + lift * noise))
        actual_units = int(planned_units * float(rng.uniform(0.85, 1.05)))
        base_promo_window = base_units_week * dur
        realized_lift = round((actual_units - base_promo_window) / max(base_promo_window, 1), 4)

        spend_per_unit = disc * sku["list_price"] * (1 - ret["coop_funding_pct"])
        planned_spend = round(planned_units * spend_per_unit, 2)
        actual_spend = round(actual_units * spend_per_unit * float(rng.uniform(0.93, 1.02)), 2)

        rows.append({
            "promo_id": f"PROMO-{promo_num:04d}",
            "sku_id": sku["sku_id"],
            "retailer_id": ret["retailer_id"],
            "start_week": start_wk,
            "end_week": end_wk,
            "mechanic": mech,
            "discount_depth_pct": disc,
            "planned_units": planned_units,
            "planned_spend": planned_spend,
            "actual_units": actual_units,
            "actual_spend": actual_spend,
            "realized_lift_pct": max(realized_lift, 0.0),
        })
        promo_num += 1

    return pd.DataFrame(rows)


def generate_sales_history(
    sku_master: pd.DataFrame,
    retailer_master: pd.DataFrame,
    calendar: pd.DataFrame,
    promo_history: pd.DataFrame,
) -> pd.DataFrame:
    # Build a fast lookup: (week_id, sku_id, retailer_id) → promo_id, discount_depth
    promo_lookup: dict = {}
    for _, p in promo_history.iterrows():
        wks = calendar[
            (calendar["week_id"] >= p["start_week"]) & (calendar["week_id"] <= p["end_week"])
        ]["week_id"].tolist()
        for w in wks:
            key = (w, p["sku_id"], p["retailer_id"])
            promo_lookup[key] = (p["promo_id"], p["discount_depth_pct"], p["mechanic"])

    rows = []
    weeks = calendar["week_id"].tolist()
    week_season = dict(zip(calendar["week_id"], calendar["season"]))
    week_festival = dict(zip(calendar["week_id"], calendar["festival_flag"]))

    for _, sku in sku_master.iterrows():
        cat = sku["category"]
        cat_params = CATEGORY_PARAMS.get(cat, {"elasticity": 2.0, "base_vel": 200})
        base_vel = cat_params["base_vel"]
        elast = cat_params["elasticity"]

        for _, ret in retailer_master.iterrows():
            # Skip some inactive combos (Traditional Trade carries fewer SKUs)
            if ret["tier"] == "Tier 3" and rng.random() < 0.30:
                continue

            tier_mult = {"Tier 1": 1.5, "Tier 2": 0.8, "Tier 3": 0.25}[ret["tier"]]
            base_units_wk = max(5, int(base_vel * tier_mult * float(rng.uniform(0.7, 1.3))))

            for wk in weeks:
                # Skip if SKU launched after this week
                if sku["launch_date"] > calendar[calendar["week_id"] == wk].iloc[0]["week_start_date"]:
                    continue

                s_mult = SEASON_MULT.get(week_season.get(wk, "Summer"), 1.0)
                if week_festival.get(wk):
                    s_mult = FESTIVAL_MULT

                baseline = max(1, int(base_units_wk * s_mult * float(rng.normal(1.0, 0.05))))

                promo_info = promo_lookup.get((wk, sku["sku_id"], ret["retailer_id"]))
                if promo_info:
                    promo_id, disc, mech = promo_info
                    lift = elast * disc * MECHANIC_MULT.get(mech, 1.0) * s_mult
                    noise = float(rng.normal(1.0, 0.12))
                    units_sold = max(baseline, int(baseline * (1 + lift * noise)))
                    realized_price = sku["list_price"] * (1 - disc)
                    on_promo = True
                else:
                    promo_id = ""
                    units_sold = max(1, int(baseline * float(rng.normal(1.0, 0.04))))
                    realized_price = sku["list_price"]
                    on_promo = False

                gross_rev = round(units_sold * realized_price, 2)

                rows.append({
                    "week_id": wk,
                    "sku_id": sku["sku_id"],
                    "retailer_id": ret["retailer_id"],
                    "units_sold": units_sold,
                    "gross_revenue": gross_rev,
                    "on_promo_flag": on_promo,
                    "baseline_units": baseline,
                    "promo_id": promo_id,
                })

    return pd.DataFrame(rows)


def generate_trade_spend_ledger(promo_history: pd.DataFrame) -> pd.DataFrame:
    spend_types = ["Off-Invoice", "Scan-Back", "Slotting", "Display Fee", "Co-op"]
    rows = []
    txn_num = 1

    for _, p in promo_history.iterrows():
        total = p["actual_spend"]
        n_lines = int(rng.integers(2, 4))
        splits = rng.dirichlet(np.ones(n_lines)) * total

        start_date = pd.to_datetime(p["start_week"] + "-1", format="%G-W%V-%u").date()
        y = start_date.year
        m = start_date.month
        q = (m - 1) // 3 + 1
        period = f"{y}-Q{q}"

        for j, amt in enumerate(splits):
            stype = spend_types[j % len(spend_types)]
            posted = start_date + timedelta(days=int(rng.integers(0, 14)))
            rows.append({
                "transaction_id": f"TXN-{txn_num:05d}",
                "promo_id": p["promo_id"],
                "retailer_id": p["retailer_id"],
                "spend_type": stype,
                "amount": round(float(amt), 2),
                "posted_date": posted.isoformat(),
                "period": period,
            })
            txn_num += 1

    return pd.DataFrame(rows)


def main():
    print("Generating synthetic CPG data…")
    cal = generate_calendar()
    cal.to_csv(OUTPUT_DIR / "calendar.csv", index=False)
    print(f"  calendar.csv          {len(cal)} rows")

    skus = generate_sku_master()
    skus.to_csv(OUTPUT_DIR / "sku_master.csv", index=False)
    print(f"  sku_master.csv        {len(skus)} rows")

    rets = generate_retailer_master()
    rets.to_csv(OUTPUT_DIR / "retailer_master.csv", index=False)
    print(f"  retailer_master.csv   {len(rets)} rows")

    cannibal = generate_cannibalization_matrix(skus)
    cannibal.to_csv(OUTPUT_DIR / "cannibalization_matrix.csv", index=False)
    print(f"  cannibalization_matrix.csv  {len(cannibal)} rows")

    promos = generate_promo_history(skus, rets, cal)
    promos.to_csv(OUTPUT_DIR / "promo_history.csv", index=False)
    print(f"  promo_history.csv     {len(promos)} rows")

    print("  Generating sales_history.csv (this may take ~30s)…")
    sales = generate_sales_history(skus, rets, cal, promos)
    sales.to_csv(OUTPUT_DIR / "sales_history.csv", index=False)
    print(f"  sales_history.csv     {len(sales)} rows")

    ledger = generate_trade_spend_ledger(promos)
    ledger.to_csv(OUTPUT_DIR / "trade_spend_ledger.csv", index=False)
    print(f"  trade_spend_ledger.csv {len(ledger)} rows")

    print("Done.")


if __name__ == "__main__":
    main()
