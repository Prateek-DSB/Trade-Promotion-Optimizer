"""
Price-elasticity based promo lift model.
Lift is estimated as: elasticity × discount_depth × mechanic_multiplier × seasonal_multiplier
Returns point estimate and a ±15% confidence interval.
"""

import pandas as pd

CATEGORY_ELASTICITY = {
    "Coffee":   2.5,
    "Tea":      2.0,
    "Juice":    1.5,
    "Chips":    2.0,
    "Biscuits": 1.8,
}

MECHANIC_MULTIPLIER = {
    "Price Off": 1.0,
    "BOGO":      1.8,
    "Display":   0.6,
    "Feature":   0.8,
    "Combo":     0.7,
}

SEASON_MULTIPLIER = {
    "Winter":  1.10,
    "Summer":  0.90,
    "Monsoon": 0.95,
    "Festive": 1.25,
}

FESTIVAL_MULTIPLIER = 1.40


def _get_week_context(
    start_week: str,
    end_week: str,
    calendar: pd.DataFrame,
) -> tuple[str, str]:
    """Return (dominant_season, festival_flag) for a promo window."""
    mask = (calendar["week_id"] >= start_week) & (calendar["week_id"] <= end_week)
    window = calendar[mask]
    if window.empty:
        return "Summer", ""
    season = window["season"].mode().iloc[0]
    festivals = window[window["festival_flag"] != ""]["festival_flag"]
    festival = festivals.iloc[0] if not festivals.empty else ""
    return season, festival


def estimate_lift(
    sku_id: str,
    retailer_id: str,
    mechanic: str,
    discount_depth_pct: float,
    start_week: str,
    end_week: str,
    sku_master: pd.DataFrame,
    calendar: pd.DataFrame,
) -> dict:
    """
    Returns a lift estimate for a single promo event.

    Returns
    -------
    dict with keys:
        lift_pct          – point estimate (fraction of baseline)
        lift_pct_low      – lower bound of 85% CI
        lift_pct_high     – upper bound of 85% CI
        elasticity_used   – category elasticity applied
        season            – season during promo
        festival          – festival name if applicable, else ""
        mechanic_mult     – multiplier applied for the mechanic
        seasonal_mult     – multiplier applied for the season/festival
    """
    sku_row = sku_master[sku_master["sku_id"] == sku_id]
    if sku_row.empty:
        return {"error": f"SKU {sku_id} not found"}

    category = sku_row.iloc[0]["category"]
    elasticity = CATEGORY_ELASTICITY.get(category, 2.0)
    mech_mult = MECHANIC_MULTIPLIER.get(mechanic, 1.0)

    season, festival = _get_week_context(start_week, end_week, calendar)
    if festival:
        s_mult = FESTIVAL_MULTIPLIER
    else:
        s_mult = SEASON_MULTIPLIER.get(season, 1.0)

    lift_pct = elasticity * discount_depth_pct * mech_mult * s_mult
    # ±15% CI
    lift_pct_low = round(lift_pct * 0.85, 4)
    lift_pct_high = round(lift_pct * 1.15, 4)
    lift_pct = round(lift_pct, 4)

    return {
        "lift_pct":        lift_pct,
        "lift_pct_low":    lift_pct_low,
        "lift_pct_high":   lift_pct_high,
        "elasticity_used": elasticity,
        "season":          season,
        "festival":        festival,
        "mechanic_mult":   mech_mult,
        "seasonal_mult":   round(s_mult, 3),
    }


def estimate_incremental_units(
    baseline_units_per_week: float,
    num_weeks: int,
    lift_pct: float,
) -> dict:
    """
    Convert a lift percentage into absolute incremental units.

    Returns
    -------
    dict with baseline_total, incremental_units, total_promo_units
    """
    baseline_total = baseline_units_per_week * num_weeks
    incremental = baseline_total * lift_pct
    total = baseline_total + incremental
    return {
        "baseline_total":    round(baseline_total),
        "incremental_units": round(incremental),
        "total_promo_units": round(total),
    }
