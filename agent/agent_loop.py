"""
Agentic tool-use loop backed by Claude.
Temperature 0 for determinism. Every turn produces a full trace.
"""

import json
import time
import os
import anthropic
from agent.tools import TOOL_DEFINITIONS, execute_tool
from agent.rules_parser import format_rules_for_context

MODEL = "claude-sonnet-4-6"
MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT_TEMPLATE = """You are a Trade Promotion ROI Optimizer co-pilot for CPG Revenue Growth Management.

Your job: help Trade Marketing Managers build, simulate, and compare quarterly promotional plans that maximise incremental ROI while complying with all business rules.

MANDATORY WORKFLOW — follow this EVERY time the user asks for a plan or recommendation:
1. Call get_applicable_rules to retrieve relevant rules BEFORE proposing anything.
2. Call get_baseline_forecast for each SKU × retailer combination you intend to include.
3. Call estimate_promo_lift for each candidate event.
4. Call simulate_plan with the full event list to get ROI, cannibalization adjustments, and compliance check.
5. If compliance_violations is non-empty, iterate: adjust the plan and re-simulate.
6. Present the recommended plan with: ROI, total spend, rule IDs consulted (cite every rule from step 1), and a plain-English rationale that explains trade-offs.

RESPONSE FORMAT for plan recommendations:
- Lead with the headline: plan ROI, total spend, number of promotions, compliance status.
- List rule IDs checked and whether each fired or passed.
- Explain why each promo was selected or rejected.
- If violations exist, explain them clearly and propose a compliant alternative.

IMPORTANT — ALWAYS use the exact sku_id and retailer_id values from the catalog below when calling any tool. Never guess or invent IDs. When the user mentions a brand name (e.g. "BrewCo"), category (e.g. "Coffee"), or retailer name (e.g. "BigMart"), look up the matching IDs in the catalog and use those.

{catalog_context}

{rules_context}
"""


class DataStore:
    """Holds all DataFrames loaded for the session."""
    def __init__(self):
        self.sku_master = None
        self.retailer_master = None
        self.calendar = None
        self.sales_history = None
        self.promo_history = None
        self.trade_spend_ledger = None
        self.cannibalization_matrix = None

    @property
    def is_loaded(self) -> bool:
        return all(df is not None for df in [
            self.sku_master, self.retailer_master, self.calendar,
            self.sales_history, self.promo_history, self.cannibalization_matrix,
        ])


def _format_catalog_context(data_store: DataStore) -> str:
    lines = []
    if data_store.sku_master is not None:
        lines.append("AVAILABLE SKUs (use these exact sku_id values in tool calls):")
        for _, row in data_store.sku_master.iterrows():
            lines.append(
                f"  {row['sku_id']}: {row['sku_name']} "
                f"(brand={row['brand']}, category={row['category']}, list_price=₹{row['list_price']:.0f})"
            )
    if data_store.retailer_master is not None:
        lines.append("\nAVAILABLE RETAILERS (use these exact retailer_id values in tool calls):")
        for _, row in data_store.retailer_master.iterrows():
            lines.append(
                f"  {row['retailer_id']}: {row['retailer_name']} "
                f"(channel={row['channel']}, region={row['region']}, tier={row['tier']})"
            )
    return "\n".join(lines) if lines else "(No catalog loaded — ask user to load data files)"


def run_agent_turn(
    user_message: str,
    conversation_history: list[dict],
    data_store: DataStore,
    scenarios_store: dict,
    rules_store: list[dict],
) -> tuple[str, list[dict], list[dict]]:
    """
    Run one conversational turn of the agent.

    Returns
    -------
    (assistant_text, updated_conversation_history, trace)
        trace – list of dicts describing each step (tool calls + results)
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "⚠️ ANTHROPIC_API_KEY not set. Please add it to your environment variables.",
            conversation_history,
            [],
        )

    client = anthropic.Anthropic(api_key=api_key)
    rules_context = format_rules_for_context(rules_store) if rules_store else "(No rules loaded)"
    catalog_context = _format_catalog_context(data_store)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        rules_context=rules_context,
        catalog_context=catalog_context,
    )

    messages = conversation_history + [{"role": "user", "content": user_message}]
    trace = []
    t_start = time.time()

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if not tool_uses:
            # Final text response
            final_text = "\n".join(b.text for b in text_blocks)
            elapsed = round(time.time() - t_start, 2)
            trace.append({
                "step": "final_response",
                "text_length": len(final_text),
                "elapsed_sec": elapsed,
                "stop_reason": response.stop_reason,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            })
            # Updated history (append the user turn + all assistant turns)
            updated_history = messages
            return final_text, updated_history, trace

        # Execute tool calls
        tool_results = []
        for tu in tool_uses:
            t_tool_start = time.time()
            result = execute_tool(
                tool_name=tu.name,
                tool_input=tu.input,
                data_store=data_store,
                scenarios_store=scenarios_store,
                rules_store=rules_store,
            )
            t_tool_elapsed = round(time.time() - t_tool_start, 3)
            trace.append({
                "step": "tool_call",
                "tool_name": tu.name,
                "tool_input": tu.input,
                "tool_result_summary": _summarise_result(tu.name, result),
                "elapsed_sec": t_tool_elapsed,
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})

    # Safety fallback if max rounds exceeded
    return (
        "I've reached the maximum tool-call depth. Please try a more specific request.",
        messages,
        trace,
    )


def _summarise_result(tool_name: str, result: dict) -> str:
    """One-line summary of a tool result for the trace log."""
    if "error" in result:
        return f"ERROR: {result['error']}"
    if tool_name == "get_baseline_forecast":
        return (f"baseline {result.get('projected_weekly_baseline_units')} units/wk "
                f"(YoY trend {result.get('yoy_trend')})")
    if tool_name == "estimate_promo_lift":
        return (f"lift {result.get('lift_pct', 0):.1%} → "
                f"{result.get('incremental_units', 0)} incremental units")
    if tool_name == "simulate_plan":
        v = len(result.get("compliance_violations", []))
        return (f"ROI {result.get('plan_roi')}, spend ₹{result.get('total_brand_spend_inr', 0):,.0f}, "
                f"{v} violation(s)")
    if tool_name == "compare_scenarios":
        n = len(result.get("comparison", []))
        return f"{n} scenario(s) compared"
    if tool_name == "get_applicable_rules":
        return f"{result.get('rules_retrieved', 0)} rule(s) retrieved"
    return str(result)[:120]
