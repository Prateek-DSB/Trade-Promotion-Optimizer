"""
Compliance Check module — validates a candidate plan against all 17 business rules
from business_rules.docx v1.0.

Each violation dict contains:
    rule_id        – e.g. "RULE-D01"
    rule_statement – short description
    detail         – why this specific event/plan fired the rule
    promo_id       – affected promo identifier (if applicable)
    severity       – "blocker" (must fix) or "warning" (should review)
"""

import pandas as pd
from datetime import date, timedelta


BUDGET_CAP = 50_000_000          # RULE-B01
TIER1_SPEND_MIN = 0.35           # RULE-B02
TIER1_SPEND_MAX = 0.55           # RULE-B02
SKU_SPEND_MAX_RATIO = 0.12       # RULE-B03
PREMIUM_PRICE_THRESHOLD = 400    # RULE-D01
PREMIUM_MAX_DISCOUNT = 0.15      # RULE-D01
MAX_DISCOUNT = 0.30              # RULE-D02
MIN_DISCOUNT = 0.05              # RULE-D03
BOGO_MIN_MARGIN = 0.40           # RULE-M01
DISPLAY_MIN_WEEKS = 2            # RULE-M03 (14 days = 2 weeks)
TIER1_MIN_PROMOS = 4             # RULE-C01
FESTIVAL_MIN_SKUS = 6            # RULE-C02
MAX_PROMO_WEEKS_IN_13 = 10       # RULE-C03
NEW_LAUNCH_DAYS = 90             # RULE-E01
CANNIBAL_THRESHOLD = 0.20        # RULE-X01


def _week_count(start_week: str, end_week: str, calendar: pd.DataFrame) -> int:
    mask = (calendar["week_id"] >= start_week) & (calendar["week_id"] <= end_week)
    return int(mask.sum())


def _weeks_in_window(start_week: str, weeks_back: int, calendar: pd.DataFrame) -> list[str]:
    """Return the 'weeks_back' weeks ending at start_week (inclusive)."""
    idx = calendar[calendar["week_id"] <= start_week].index.tolist()
    if not idx:
        return []
    end_pos = max(idx)
    start_pos = max(0, end_pos - weeks_back + 1)
    return calendar.loc[start_pos:end_pos, "week_id"].tolist()


def check_compliance(
    plan_events: list[dict],
    sku_master: pd.DataFrame,
    retailer_master: pd.DataFrame,
    calendar: pd.DataFrame,
    cannibalization_matrix: pd.DataFrame,
    promo_history: pd.DataFrame | None = None,
    quarter: str | None = None,
) -> list[dict]:
    """
    Validate a list of plan_events against all active business rules.

    plan_events items must contain:
        promo_id, sku_id, retailer_id, start_week, end_week,
        mechanic, discount_depth_pct, planned_spend

    Returns a list of violation dicts (empty list = fully compliant).
    """
    violations = []
    sku_idx = sku_master.set_index("sku_id")
    ret_idx = retailer_master.set_index("retailer_id")
    cannibal_idx = cannibalization_matrix.set_index(["sku_a", "sku_b"])["cross_elasticity"].to_dict()
    calendar_wk_set = set(calendar["week_id"])

    total_spend = sum(e.get("planned_spend", 0) for e in plan_events)

    # ── RULE-B01 ─────────────────────────────────────────────────────────────
    if total_spend > BUDGET_CAP:
        violations.append({
            "rule_id": "RULE-B01",
            "rule_statement": "Quarterly trade budget cap is ₹50,000,000",
            "detail": f"Plan total spend ₹{total_spend:,.0f} exceeds cap ₹{BUDGET_CAP:,.0f}",
            "promo_id": None,
            "severity": "blocker",
        })

    # ── RULE-B02 ─────────────────────────────────────────────────────────────
    tier1_ids = set(ret_idx[ret_idx["tier"] == "Tier 1"].index)
    tier1_spend = sum(e.get("planned_spend", 0) for e in plan_events
                      if e.get("retailer_id") in tier1_ids)
    if total_spend > 0:
        t1_ratio = tier1_spend / total_spend
        if not (TIER1_SPEND_MIN <= t1_ratio <= TIER1_SPEND_MAX):
            violations.append({
                "rule_id": "RULE-B02",
                "rule_statement": "Tier 1 retailers must receive 35%–55% of total trade spend",
                "detail": f"Tier 1 spend ratio is {t1_ratio:.1%} (allowed 35%–55%)",
                "promo_id": None,
                "severity": "blocker",
            })

    # ── RULE-B03 ─────────────────────────────────────────────────────────────
    from collections import defaultdict
    sku_spend: dict[str, float] = defaultdict(float)
    for e in plan_events:
        sku_spend[e["sku_id"]] += e.get("planned_spend", 0)
    for sku_id, spend in sku_spend.items():
        if total_spend > 0 and spend / total_spend > SKU_SPEND_MAX_RATIO:
            violations.append({
                "rule_id": "RULE-B03",
                "rule_statement": "No single SKU may exceed 12% of quarterly trade spend",
                "detail": f"{sku_id} represents {spend/total_spend:.1%} of spend (limit 12%)",
                "promo_id": None,
                "severity": "blocker",
            })

    for ev in plan_events:
        sku_id = ev.get("sku_id", "")
        ret_id = ev.get("retailer_id", "")
        promo_id = ev.get("promo_id", "?")
        disc = ev.get("discount_depth_pct", 0)
        mech = ev.get("mechanic", "")
        start_wk = ev.get("start_week", "")
        end_wk = ev.get("end_week", "")

        if sku_id not in sku_idx.index:
            continue
        sku_row = sku_idx.loc[sku_id]
        ret_row = ret_idx.loc[ret_id] if ret_id in ret_idx.index else None

        # ── RULE-D01 ──────────────────────────────────────────────────────────
        if sku_row["list_price"] > PREMIUM_PRICE_THRESHOLD and disc > PREMIUM_MAX_DISCOUNT:
            violations.append({
                "rule_id": "RULE-D01",
                "rule_statement": "Premium SKUs (list price > ₹400) capped at 15% discount",
                "detail": f"{sku_id} ({sku_row['sku_name']}) priced ₹{sku_row['list_price']:.0f} "
                          f"discounted at {disc:.0%} — exceeds 15% cap",
                "promo_id": promo_id,
                "severity": "blocker",
            })

        # ── RULE-D02 ──────────────────────────────────────────────────────────
        if disc > MAX_DISCOUNT:
            violations.append({
                "rule_id": "RULE-D02",
                "rule_statement": "Maximum allowed discount depth is 30%",
                "detail": f"{sku_id} discount {disc:.0%} exceeds 30% maximum",
                "promo_id": promo_id,
                "severity": "blocker",
            })

        # ── RULE-D03 ──────────────────────────────────────────────────────────
        if disc < MIN_DISCOUNT:
            violations.append({
                "rule_id": "RULE-D03",
                "rule_statement": "Minimum discount to qualify as a promotion is 5%",
                "detail": f"{sku_id} discount {disc:.0%} is below 5% minimum",
                "promo_id": promo_id,
                "severity": "warning",
            })

        # ── RULE-M01 ──────────────────────────────────────────────────────────
        if mech == "BOGO" and sku_row["gross_margin_pct"] <= BOGO_MIN_MARGIN:
            violations.append({
                "rule_id": "RULE-M01",
                "rule_statement": "BOGO mechanic restricted to SKUs with gross margin > 40%",
                "detail": f"{sku_id} gross margin {sku_row['gross_margin_pct']:.0%} ≤ 40%",
                "promo_id": promo_id,
                "severity": "blocker",
            })

        # ── RULE-M02 ──────────────────────────────────────────────────────────
        if mech == "Combo":
            combo_skus = ev.get("combo_sku_ids", [sku_id])
            subcats = set()
            for s in combo_skus:
                if s in sku_idx.index:
                    subcats.add(sku_idx.loc[s, "subcategory"])
            if len(subcats) < 2:
                violations.append({
                    "rule_id": "RULE-M02",
                    "rule_statement": "Combo must include SKUs from at least two different subcategories",
                    "detail": f"Combo event {promo_id} only spans subcategory: {subcats}",
                    "promo_id": promo_id,
                    "severity": "blocker",
                })

        # ── RULE-M03 ──────────────────────────────────────────────────────────
        if mech == "Display":
            dur_weeks = _week_count(start_wk, end_wk, calendar)
            if dur_weeks < DISPLAY_MIN_WEEKS:
                violations.append({
                    "rule_id": "RULE-M03",
                    "rule_statement": "Display promotions require a minimum 14-day (2-week) commitment",
                    "detail": f"{promo_id}: Display mechanic spans only {dur_weeks} week(s)",
                    "promo_id": promo_id,
                    "severity": "blocker",
                })

        # ── RULE-E01 ──────────────────────────────────────────────────────────
        launch_str = str(sku_row.get("launch_date", "2020-01-01"))
        try:
            launch_date = date.fromisoformat(launch_str)
        except ValueError:
            launch_date = date(2020, 1, 1)
        start_cal = calendar[calendar["week_id"] == start_wk]
        if not start_cal.empty:
            promo_start_date = date.fromisoformat(start_cal.iloc[0]["week_start_date"])
            days_since_launch = (promo_start_date - launch_date).days
            if 0 <= days_since_launch < NEW_LAUNCH_DAYS:
                violations.append({
                    "rule_id": "RULE-E01",
                    "rule_statement": "SKUs launched within last 90 days are ineligible for promotion",
                    "detail": f"{sku_id} launched {launch_str}, only {days_since_launch} days before this promo",
                    "promo_id": promo_id,
                    "severity": "blocker",
                })

        # ── RULE-C03 ──────────────────────────────────────────────────────────
        window_13 = _weeks_in_window(end_wk, 13, calendar)
        candidate_weeks = set(calendar[
            (calendar["week_id"] >= start_wk) & (calendar["week_id"] <= end_wk)
        ]["week_id"].tolist())

        # Count promo weeks from promo_history + this plan
        existing_promo_weeks = set()
        if promo_history is not None:
            hist_for_sku = promo_history[
                (promo_history["sku_id"] == sku_id) &
                (promo_history["retailer_id"] == ret_id)
            ]
            for _, hp in hist_for_sku.iterrows():
                hw = calendar[
                    (calendar["week_id"] >= hp["start_week"]) &
                    (calendar["week_id"] <= hp["end_week"])
                ]["week_id"].tolist()
                existing_promo_weeks.update(hw)

        plan_promo_weeks_in_window = set(w for w in candidate_weeks if w in window_13)
        hist_promo_weeks_in_window = set(w for w in existing_promo_weeks if w in window_13)
        total_promo_weeks_in_13 = len(plan_promo_weeks_in_window | hist_promo_weeks_in_window)

        if total_promo_weeks_in_13 > MAX_PROMO_WEEKS_IN_13:
            violations.append({
                "rule_id": "RULE-C03",
                "rule_statement": "No SKU may be on promo more than 10 weeks in any 13-week window",
                "detail": f"{sku_id} at {ret_id} would be on promo {total_promo_weeks_in_13} "
                          f"weeks in the 13-week window ending {end_wk}",
                "promo_id": promo_id,
                "severity": "blocker",
            })

    # ── RULE-C01 ─────────────────────────────────────────────────────────────
    tier1_promo_counts: dict[str, set] = defaultdict(set)
    for ev in plan_events:
        ret_id = ev.get("retailer_id", "")
        if ret_id in tier1_ids:
            tier1_promo_counts[ret_id].add(ev.get("promo_id", ev.get("sku_id", "")))
    for ret_id in tier1_ids:
        count = len(tier1_promo_counts.get(ret_id, set()))
        if count < TIER1_MIN_PROMOS:
            ret_name = ret_idx.loc[ret_id, "retailer_name"] if ret_id in ret_idx.index else ret_id
            violations.append({
                "rule_id": "RULE-C01",
                "rule_statement": "Each Tier 1 retailer must run at least 4 promotions per quarter",
                "detail": f"{ret_name} ({ret_id}) has only {count} promo(s) planned",
                "promo_id": None,
                "severity": "blocker",
            })

    # ── RULE-C02 ─────────────────────────────────────────────────────────────
    festival_weeks = calendar[calendar["festival_flag"] != ""][["week_id", "festival_flag"]]
    plan_weeks_set = set()
    for ev in plan_events:
        ws = ev.get("start_week", "")
        we = ev.get("end_week", "")
        mask = (calendar["week_id"] >= ws) & (calendar["week_id"] <= we)
        plan_weeks_set.update(calendar[mask]["week_id"].tolist())

    for _, fw_row in festival_weeks.iterrows():
        fw = fw_row["week_id"]
        if fw not in plan_weeks_set:
            continue
        active_skus = set(
            ev["sku_id"] for ev in plan_events
            if ev.get("start_week", "") <= fw <= ev.get("end_week", "")
        )
        if len(active_skus) < FESTIVAL_MIN_SKUS:
            violations.append({
                "rule_id": "RULE-C02",
                "rule_statement": "Festival weeks require active promotions on at least 6 flagship SKUs",
                "detail": f"Festival week {fw} ({fw_row['festival_flag']}) has only "
                          f"{len(active_skus)} SKU(s) on promo (need ≥ 6)",
                "promo_id": None,
                "severity": "blocker",
            })

    # ── RULE-X01 ─────────────────────────────────────────────────────────────
    week_order = {w: i for i, w in enumerate(calendar["week_id"].tolist())}

    def overlaps(a, b):
        return (week_order.get(a["start_week"], 0) <= week_order.get(b["end_week"], 0) and
                week_order.get(b["start_week"], 0) <= week_order.get(a["end_week"], 0))

    for i, ev_a in enumerate(plan_events):
        for ev_b in plan_events[i + 1:]:
            if ev_a["retailer_id"] != ev_b["retailer_id"]:
                continue
            if not overlaps(ev_a, ev_b):
                continue
            ce = cannibal_idx.get((ev_a["sku_id"], ev_b["sku_id"]), 0.0)
            ce_rev = cannibal_idx.get((ev_b["sku_id"], ev_a["sku_id"]), 0.0)
            ce_max = max(ce, ce_rev)
            if ce_max > CANNIBAL_THRESHOLD:
                violations.append({
                    "rule_id": "RULE-X01",
                    "rule_statement": "SKU pairs with cross-elasticity > 0.20 cannot be simultaneously promoted at the same retailer",
                    "detail": f"{ev_a['sku_id']} & {ev_b['sku_id']} at {ev_a['retailer_id']} "
                              f"overlap (cross-elasticity {ce_max:.2f})",
                    "promo_id": f"{ev_a.get('promo_id','?')} + {ev_b.get('promo_id','?')}",
                    "severity": "blocker",
                })

    return violations
