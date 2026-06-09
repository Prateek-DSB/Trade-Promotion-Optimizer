"""
ROI calculator following CPG industry standard:
    Incremental Gross Profit = net_incremental_units × (promo_price - COGS)
    Trade Investment (brand share) = total_promo_units × discount_per_unit × (1 - coop_funding_pct)
    ROI = Incremental GP / Trade Investment
"""

import pandas as pd


def calculate_promo_roi(
    sku_id: str,
    retailer_id: str,
    discount_depth_pct: float,
    total_promo_units: int,
    net_incremental_units: int,
    sku_master: pd.DataFrame,
    retailer_master: pd.DataFrame,
) -> dict:
    """
    Calculate ROI for a single promo event.

    Returns
    -------
    dict with:
        list_price, cogs_per_unit, promo_price, gross_margin_at_promo
        brand_trade_investment_inr
        incremental_gross_profit_inr
        roi                         – incremental GP / trade investment
        incremental_revenue_inr
    """
    sku_row = sku_master[sku_master["sku_id"] == sku_id]
    ret_row = retailer_master[retailer_master["retailer_id"] == retailer_id]
    if sku_row.empty or ret_row.empty:
        return {"error": f"SKU {sku_id} or retailer {retailer_id} not found"}

    list_price = float(sku_row.iloc[0]["list_price"])
    cogs = float(sku_row.iloc[0]["cogs_per_unit"])
    coop = float(ret_row.iloc[0]["coop_funding_pct"])

    promo_price = list_price * (1 - discount_depth_pct)
    gross_margin_at_promo = promo_price - cogs

    # Incremental revenue and margin
    incremental_revenue = net_incremental_units * promo_price
    incremental_gp = net_incremental_units * gross_margin_at_promo

    # Trade investment = brand's share of discount on all promo units
    discount_per_unit = list_price * discount_depth_pct
    trade_invest = total_promo_units * discount_per_unit * (1 - coop)

    roi = round(incremental_gp / trade_invest, 3) if trade_invest > 0 else 0.0

    return {
        "list_price":                   round(list_price, 2),
        "cogs_per_unit":                round(cogs, 2),
        "promo_price":                  round(promo_price, 2),
        "gross_margin_at_promo":        round(gross_margin_at_promo, 2),
        "brand_trade_investment_inr":   round(trade_invest, 2),
        "incremental_gross_profit_inr": round(incremental_gp, 2),
        "incremental_revenue_inr":      round(incremental_revenue, 2),
        "roi":                          roi,
    }


def calculate_plan_summary(events_with_roi: list[dict]) -> dict:
    """
    Aggregate ROI metrics across all events in a plan.
    """
    total_invest = sum(e.get("brand_trade_investment_inr", 0) for e in events_with_roi)
    total_igp = sum(e.get("incremental_gross_profit_inr", 0) for e in events_with_roi)
    total_rev = sum(e.get("incremental_revenue_inr", 0) for e in events_with_roi)

    plan_roi = round(total_igp / total_invest, 3) if total_invest > 0 else 0.0

    return {
        "total_brand_spend_inr":            round(total_invest, 2),
        "total_incremental_gp_inr":         round(total_igp, 2),
        "total_incremental_revenue_inr":    round(total_rev, 2),
        "plan_roi":                         plan_roi,
        "num_promo_events":                 len(events_with_roi),
    }
