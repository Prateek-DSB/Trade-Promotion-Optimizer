"""
Five agent tools for the Trade Promotion ROI Optimizer.
Each tool is implemented as a Python function and paired with a Claude tool definition.
"""

import uuid
import pandas as pd
from analytics.lift_model import estimate_lift, estimate_incremental_units
from analytics.cannibalization import apply_cannibalization_adjustment
from analytics.roi_calculator import calculate_promo_roi, calculate_plan_summary
from analytics.compliance_check import check_compliance


# ── Tool definitions for the Claude API ──────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_baseline_forecast",
        "description": (
            "Retrieve the baseline (non-promo) weekly sales forecast for a SKU at a retailer "
            "for a given quarter. Uses the prior year's same quarter as the benchmark, "
            "adjusted for trend. Returns average weekly baseline units and revenue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_id": {
                    "type": "string",
                    "description": "SKU identifier, e.g. SKU-0001"
                },
                "retailer_id": {
                    "type": "string",
                    "description": "Retailer identifier, e.g. RET-001"
                },
                "quarter": {
                    "type": "string",
                    "description": "Quarter in format Q{n}-YYYY, e.g. Q3-2025"
                },
            },
            "required": ["sku_id", "retailer_id", "quarter"],
        },
    },
    {
        "name": "estimate_promo_lift",
        "description": (
            "Estimate the incremental unit lift for a single promotional event using the "
            "price-elasticity model. Returns lift percentage, incremental units, and a "
            "confidence interval. Accounts for the mechanic type and seasonal context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_id":             {"type": "string"},
                "retailer_id":        {"type": "string"},
                "mechanic":           {"type": "string",
                                       "enum": ["Price Off", "BOGO", "Display", "Feature", "Combo"]},
                "discount_depth_pct": {"type": "number",
                                       "description": "Discount depth as a decimal, e.g. 0.15 for 15%"},
                "start_week":         {"type": "string",
                                       "description": "ISO week, e.g. 2025-W14"},
                "end_week":           {"type": "string",
                                       "description": "ISO week, e.g. 2025-W17"},
            },
            "required": ["sku_id", "retailer_id", "mechanic", "discount_depth_pct",
                         "start_week", "end_week"],
        },
    },
    {
        "name": "simulate_plan",
        "description": (
            "Simulate a complete promotional plan — a list of promo events — and return "
            "full ROI metrics, cannibalization-adjusted incremental units, total trade spend, "
            "and a compliance check against all business rules. The agent MUST call this "
            "before recommending any plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_name": {"type": "string",
                              "description": "Human-readable name for this scenario"},
                "quarter":   {"type": "string",
                              "description": "Planning quarter, e.g. Q3-2025"},
                "events": {
                    "type": "array",
                    "description": "List of promo events",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sku_id":             {"type": "string"},
                            "retailer_id":        {"type": "string"},
                            "mechanic":           {"type": "string"},
                            "discount_depth_pct": {"type": "number"},
                            "start_week":         {"type": "string"},
                            "end_week":           {"type": "string"},
                            "planned_spend":      {"type": "number",
                                                   "description": "Estimated brand spend in INR"},
                        },
                        "required": ["sku_id", "retailer_id", "mechanic",
                                     "discount_depth_pct", "start_week", "end_week"],
                    },
                },
            },
            "required": ["plan_name", "quarter", "events"],
        },
    },
    {
        "name": "compare_scenarios",
        "description": (
            "Compare two or more previously simulated scenarios side by side. "
            "Returns a summary table with ROI, spend, incremental revenue, "
            "and compliance status for each scenario."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scenario_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of scenario IDs returned by simulate_plan",
                },
            },
            "required": ["scenario_ids"],
        },
    },
    {
        "name": "get_applicable_rules",
        "description": (
            "Retrieve the business rules that are relevant to a given planning context. "
            "Returns rule IDs, statements, predicates, and rationale. "
            "The agent MUST call this before proposing any plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "object",
                    "description": "Planning context filters",
                    "properties": {
                        "category":   {"type": "string",
                                       "description": "SKU category filter, e.g. Coffee"},
                        "mechanic":   {"type": "string",
                                       "description": "Promo mechanic filter"},
                        "rule_category": {"type": "string",
                                          "description": "Rule category filter, e.g. Budget"},
                    },
                },
            },
            "required": ["context"],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def _get_baseline_forecast(tool_input: dict, data_store) -> dict:
    sku_id = tool_input["sku_id"]
    retailer_id = tool_input["retailer_id"]
    quarter = tool_input["quarter"]

    sales = data_store.sales_history
    cal = data_store.calendar

    # Parse quarter: Q3-2025 → 2025, Q3
    try:
        q_part, y_part = quarter.split("-")
        q_num = int(q_part[1])
        year = int(y_part)
    except Exception:
        return {"error": f"Invalid quarter format: {quarter}. Use Q{{n}}-YYYY"}

    # Current quarter weeks
    current_weeks = cal[cal["quarter"] == quarter]["week_id"].tolist()

    # Prior year same quarter for trend base
    prior_quarter = f"Q{q_num}-{year - 1}"
    prior_weeks = cal[cal["quarter"] == prior_quarter]["week_id"].tolist()

    def avg_weekly(weeks):
        if not weeks:
            return None
        subset = sales[
            (sales["sku_id"] == sku_id) &
            (sales["retailer_id"] == retailer_id) &
            (sales["week_id"].isin(weeks)) &
            (sales["on_promo_flag"] == False)
        ]
        if subset.empty:
            return None
        return {
            "avg_weekly_units": round(subset["baseline_units"].mean(), 1),
            "avg_weekly_revenue": round(subset["gross_revenue"].mean(), 2),
            "weeks_available": len(subset),
        }

    current = avg_weekly(current_weeks)
    prior = avg_weekly(prior_weeks)

    if prior is None and current is None:
        # Fall back to overall average
        overall = sales[
            (sales["sku_id"] == sku_id) &
            (sales["retailer_id"] == retailer_id) &
            (sales["on_promo_flag"] == False)
        ]
        if overall.empty:
            return {"error": f"No sales data for {sku_id} at {retailer_id}"}
        prior = {
            "avg_weekly_units": round(overall["baseline_units"].mean(), 1),
            "avg_weekly_revenue": round(overall["gross_revenue"].mean(), 2),
            "weeks_available": len(overall),
        }

    # Trend factor
    if current and prior and prior["avg_weekly_units"] > 0:
        trend = current["avg_weekly_units"] / prior["avg_weekly_units"]
    else:
        trend = 1.0

    baseline = current or prior
    projected_weekly_units = round(baseline["avg_weekly_units"] * trend, 1)
    projected_weekly_revenue = round(baseline["avg_weekly_revenue"] * trend, 2)

    sku_row = data_store.sku_master[data_store.sku_master["sku_id"] == sku_id]
    sku_name = sku_row.iloc[0]["sku_name"] if not sku_row.empty else sku_id

    return {
        "sku_id": sku_id,
        "sku_name": sku_name,
        "retailer_id": retailer_id,
        "quarter": quarter,
        "projected_weekly_baseline_units": projected_weekly_units,
        "projected_weekly_baseline_revenue_inr": projected_weekly_revenue,
        "yoy_trend": round(trend, 3),
        "data_source": f"Prior year {prior_quarter} non-promo weeks",
    }


def _estimate_promo_lift(tool_input: dict, data_store) -> dict:
    sku_id = tool_input["sku_id"]
    retailer_id = tool_input["retailer_id"]
    mechanic = tool_input["mechanic"]
    disc = tool_input["discount_depth_pct"]
    start_wk = tool_input["start_week"]
    end_wk = tool_input["end_week"]

    lift_result = estimate_lift(
        sku_id=sku_id,
        retailer_id=retailer_id,
        mechanic=mechanic,
        discount_depth_pct=disc,
        start_week=start_wk,
        end_week=end_wk,
        sku_master=data_store.sku_master,
        calendar=data_store.calendar,
    )
    if "error" in lift_result:
        return lift_result

    # Get baseline to translate to units
    cal = data_store.calendar
    num_weeks = int(cal[(cal["week_id"] >= start_wk) & (cal["week_id"] <= end_wk)].shape[0])
    num_weeks = max(1, num_weeks)

    sales = data_store.sales_history
    baseline_rows = sales[
        (sales["sku_id"] == sku_id) &
        (sales["retailer_id"] == retailer_id) &
        (sales["on_promo_flag"] == False)
    ]
    if not baseline_rows.empty:
        baseline_wk = round(baseline_rows["baseline_units"].mean(), 1)
    else:
        baseline_wk = 100.0  # fallback

    units_result = estimate_incremental_units(baseline_wk, num_weeks, lift_result["lift_pct"])

    return {
        **lift_result,
        **units_result,
        "num_promo_weeks": num_weeks,
        "baseline_weekly_units": baseline_wk,
    }


def _simulate_plan(tool_input: dict, data_store, scenarios_store: dict) -> dict:
    plan_name = tool_input["plan_name"]
    quarter = tool_input["quarter"]
    events_input = tool_input["events"]

    cal = data_store.calendar
    sales = data_store.sales_history

    enriched_events = []
    for i, ev in enumerate(events_input):
        sku_id = ev["sku_id"]
        retailer_id = ev["retailer_id"]
        start_wk = ev["start_week"]
        end_wk = ev["end_week"]
        mechanic = ev["mechanic"]
        disc = ev["discount_depth_pct"]

        promo_id = ev.get("promo_id", f"PLAN-{i+1:03d}")

        # Lift
        lift_result = estimate_lift(
            sku_id=sku_id, retailer_id=retailer_id, mechanic=mechanic,
            discount_depth_pct=disc, start_week=start_wk, end_week=end_wk,
            sku_master=data_store.sku_master, calendar=data_store.calendar,
        )
        num_weeks = max(1, int(cal[(cal["week_id"] >= start_wk) & (cal["week_id"] <= end_wk)].shape[0]))

        baseline_rows = sales[
            (sales["sku_id"] == sku_id) &
            (sales["retailer_id"] == retailer_id) &
            (sales["on_promo_flag"] == False)
        ]
        baseline_wk = round(baseline_rows["baseline_units"].mean(), 1) if not baseline_rows.empty else 100.0
        units_result = estimate_incremental_units(baseline_wk, num_weeks, lift_result.get("lift_pct", 0))

        # Planned spend (brand share)
        ret_row = data_store.retailer_master[data_store.retailer_master["retailer_id"] == retailer_id]
        sku_row = data_store.sku_master[data_store.sku_master["sku_id"] == sku_id]
        coop = float(ret_row.iloc[0]["coop_funding_pct"]) if not ret_row.empty else 0.0
        list_price = float(sku_row.iloc[0]["list_price"]) if not sku_row.empty else 100.0
        planned_spend = ev.get("planned_spend",
            round(units_result["total_promo_units"] * disc * list_price * (1 - coop), 2))

        enriched_events.append({
            "promo_id": promo_id,
            "sku_id": sku_id,
            "retailer_id": retailer_id,
            "mechanic": mechanic,
            "discount_depth_pct": disc,
            "start_week": start_wk,
            "end_week": end_wk,
            "planned_spend": planned_spend,
            "lift_pct": lift_result.get("lift_pct", 0),
            "incremental_units": units_result["incremental_units"],
            "total_promo_units": units_result["total_promo_units"],
            "baseline_total": units_result["baseline_total"],
        })

    # Cannibalization adjustment
    cannibal_adjusted = apply_cannibalization_adjustment(
        enriched_events, data_store.cannibalization_matrix, cal
    )

    # ROI per event
    events_with_roi = []
    for ev in cannibal_adjusted:
        roi_result = calculate_promo_roi(
            sku_id=ev["sku_id"],
            retailer_id=ev["retailer_id"],
            discount_depth_pct=ev["discount_depth_pct"],
            total_promo_units=ev["total_promo_units"],
            net_incremental_units=ev["net_incremental_units"],
            sku_master=data_store.sku_master,
            retailer_master=data_store.retailer_master,
        )
        events_with_roi.append({**ev, **roi_result})

    plan_summary = calculate_plan_summary(events_with_roi)

    # Compliance check
    violations = check_compliance(
        plan_events=events_with_roi,
        sku_master=data_store.sku_master,
        retailer_master=data_store.retailer_master,
        calendar=cal,
        cannibalization_matrix=data_store.cannibalization_matrix,
        promo_history=data_store.promo_history,
        quarter=quarter,
    )

    scenario_id = f"SCENARIO-{str(uuid.uuid4())[:8].upper()}"
    result = {
        "scenario_id": scenario_id,
        "plan_name": plan_name,
        "quarter": quarter,
        **plan_summary,
        "compliance_violations": violations,
        "is_compliant": len(violations) == 0,
        "events": events_with_roi,
    }

    # Persist scenario for compare_scenarios
    scenarios_store[scenario_id] = result
    return result


def _compare_scenarios(tool_input: dict, scenarios_store: dict) -> dict:
    scenario_ids = tool_input["scenario_ids"]
    rows = []
    for sid in scenario_ids:
        sc = scenarios_store.get(sid)
        if sc is None:
            rows.append({"scenario_id": sid, "error": "Scenario not found"})
            continue
        rows.append({
            "scenario_id": sid,
            "plan_name": sc["plan_name"],
            "quarter": sc["quarter"],
            "plan_roi": sc["plan_roi"],
            "total_brand_spend_inr": sc["total_brand_spend_inr"],
            "total_incremental_gp_inr": sc["total_incremental_gp_inr"],
            "total_incremental_revenue_inr": sc["total_incremental_revenue_inr"],
            "num_promo_events": sc["num_promo_events"],
            "is_compliant": sc["is_compliant"],
            "num_violations": len(sc["compliance_violations"]),
        })

    if not rows:
        return {"error": "No scenarios found"}

    best_roi = max((r.get("plan_roi", 0) for r in rows if "error" not in r), default=0)
    for r in rows:
        r["is_best_roi"] = r.get("plan_roi", 0) == best_roi

    return {"comparison": rows}


def _get_applicable_rules(tool_input: dict, rules_store: list[dict]) -> dict:
    context = tool_input.get("context", {})
    category_filter = context.get("category", "").lower()
    mechanic_filter = context.get("mechanic", "").lower()
    rule_cat_filter = context.get("rule_category", "").lower()

    matched = []
    for rule in rules_store:
        if not rule.get("active", True):
            continue
        if rule_cat_filter and rule_cat_filter not in rule["category"].lower():
            continue

        stmt_lower = rule["statement"].lower()
        pred_lower = rule["predicate"].lower()
        include = True

        if category_filter:
            # Always include Budget, Coverage, Compliance rules regardless of category
            if rule["category"] not in ("Budget", "Coverage", "Compliance"):
                include = category_filter in stmt_lower or category_filter in pred_lower

        if mechanic_filter and include:
            if rule["category"] == "Mechanic Eligibility":
                include = mechanic_filter in stmt_lower or mechanic_filter in pred_lower
                if not include:
                    include = True  # keep all mechanic rules when mechanic is specified

        if include:
            matched.append({
                "rule_id":   rule["rule_id"],
                "category":  rule["category"],
                "statement": rule["statement"],
                "predicate": rule["predicate"],
                "rationale": rule["rationale"],
                "confidence": rule["confidence"],
            })

    return {
        "rules_retrieved": len(matched),
        "context_applied": context,
        "rules": matched,
    }


# ── Dispatch ──────────────────────────────────────────────────────────────────

def execute_tool(
    tool_name: str,
    tool_input: dict,
    data_store,
    scenarios_store: dict,
    rules_store: list[dict],
) -> dict:
    if tool_name == "get_baseline_forecast":
        return _get_baseline_forecast(tool_input, data_store)
    elif tool_name == "estimate_promo_lift":
        return _estimate_promo_lift(tool_input, data_store)
    elif tool_name == "simulate_plan":
        return _simulate_plan(tool_input, data_store, scenarios_store)
    elif tool_name == "compare_scenarios":
        return _compare_scenarios(tool_input, scenarios_store)
    elif tool_name == "get_applicable_rules":
        return _get_applicable_rules(tool_input, rules_store)
    else:
        return {"error": f"Unknown tool: {tool_name}"}
