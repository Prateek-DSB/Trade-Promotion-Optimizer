"""
Cannibalization adjustment module.
For each promo event in a plan, reduces net lift by the volume stolen from
simultaneously promoted substitute SKUs at the same retailer.
Also flags pairs that violate RULE-X01 (cross_elasticity > 0.20).
"""

import pandas as pd
from itertools import combinations


def apply_cannibalization_adjustment(
    plan_events: list[dict],
    cannibalization_matrix: pd.DataFrame,
    calendar: pd.DataFrame,
) -> list[dict]:
    """
    Adjust incremental_units for each event downward by the volume stolen
    from simultaneous promos at the same retailer, and flag RULE-X01 violations.

    Parameters
    ----------
    plan_events : list of dicts, each containing:
        sku_id, retailer_id, start_week, end_week, incremental_units, lift_pct
    cannibalization_matrix : DataFrame with sku_a, sku_b, cross_elasticity
    calendar : DataFrame (used for week ordering)

    Returns
    -------
    Same list of events with added keys:
        cannibalization_loss      – units lost to/from substitute promos
        net_incremental_units     – incremental_units - cannibalization_loss
        rule_x01_violation        – bool
        rule_x01_conflict_skus    – list of conflicting SKU ids
    """
    cannibal_lookup: dict[tuple, float] = {}
    for _, row in cannibalization_matrix.iterrows():
        cannibal_lookup[(row["sku_a"], row["sku_b"])] = row["cross_elasticity"]

    week_order = {w: i for i, w in enumerate(calendar["week_id"].tolist())}

    def weeks_overlap(a_start, a_end, b_start, b_end) -> bool:
        return (
            week_order.get(a_start, 0) <= week_order.get(b_end, 0) and
            week_order.get(b_start, 0) <= week_order.get(a_end, 0)
        )

    enriched = []
    for ev in plan_events:
        loss = 0.0
        x01_conflicts = []
        for other in plan_events:
            if other is ev:
                continue
            if other["retailer_id"] != ev["retailer_id"]:
                continue
            if not weeks_overlap(ev["start_week"], ev["end_week"],
                                  other["start_week"], other["end_week"]):
                continue
            ce = cannibal_lookup.get((ev["sku_id"], other["sku_id"]), 0.0)
            if ce > 0:
                stolen = ev["incremental_units"] * ce
                loss += stolen
                if ce > 0.20:
                    x01_conflicts.append(other["sku_id"])

        net = max(0, ev["incremental_units"] - round(loss))
        enriched.append({
            **ev,
            "cannibalization_loss":   round(loss),
            "net_incremental_units":  net,
            "rule_x01_violation":     len(x01_conflicts) > 0,
            "rule_x01_conflict_skus": list(set(x01_conflicts)),
        })

    return enriched
