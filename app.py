"""
Trade Promotion ROI Optimizer — Streamlit co-pilot
Three views: Plan Builder (chat) · Scenario Compare · Rationale
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import sys
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.agent_loop import DataStore, run_agent_turn
from agent.rules_parser import parse_rules_docx, format_rules_for_context

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trade Promotion ROI Optimizer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .metric-card {
      background: #f8f9fa; border-radius: 8px; padding: 12px 16px; margin: 4px 0;
  }
  .violation-chip {
      background: #ffe0e0; color: #c0392b; border: 1px solid #e74c3c;
      padding: 3px 9px; border-radius: 12px; font-size: 0.76rem; font-weight: 600;
      display: inline-block; margin: 2px;
  }
  .pass-chip {
      background: #e0f8e0; color: #1a7a1a; border: 1px solid #27ae60;
      padding: 3px 9px; border-radius: 12px; font-size: 0.76rem; font-weight: 600;
      display: inline-block; margin: 2px;
  }
  .rule-chip {
      background: #e8f0fe; color: #1a56db; border: 1px solid #93c5fd;
      padding: 2px 8px; border-radius: 10px; font-size: 0.73rem;
      display: inline-block; margin: 2px;
  }
  .trace-step {
      background: #fafafa; border-left: 3px solid #6c757d;
      padding: 6px 12px; margin: 4px 0; border-radius: 0 4px 4px 0;
      font-size: 0.82rem; font-family: monospace;
  }
  div[data-testid="stChatMessage"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
def _init():
    for k, v in {
        "data_store":        DataStore(),
        "rules_store":       [],
        "messages":          [],   # {role, content, trace}
        "scenarios_store":   {},   # scenario_id → result dict
        "selected_cmp_ids":  [],
        "data_loaded":       False,
        "rules_loaded":      False,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ── Helper: load CSV from UploadedFile or path ─────────────────────────────────
def _read_csv(source) -> pd.DataFrame:
    if hasattr(source, "read"):
        source.seek(0)
        return pd.read_csv(source)
    return pd.read_csv(source)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Trade Promo ROI Optimizer")
    st.caption("CPG RGM Agentic Co-pilot · Portfolio v0.2")
    st.divider()

    # ── API Key ───────────────────────────────────────────────────────────────
    st.subheader("🔑 Anthropic API Key")
    api_key_input = st.text_input(
        "API Key",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if api_key_input:
        os.environ["ANTHROPIC_API_KEY"] = api_key_input
        st.success("Key set", icon="✅")
    else:
        st.warning("Required to run the agent", icon="⚠️")

    st.divider()

    # ── Data Upload ───────────────────────────────────────────────────────────
    st.subheader("📂 Upload Data Files")
    st.caption("Upload the 7 CSV data files or generate sample data below.")

    EXPECTED_CSVS = [
        "sku_master.csv",
        "retailer_master.csv",
        "calendar.csv",
        "cannibalization_matrix.csv",
        "promo_history.csv",
        "sales_history.csv",
        "trade_spend_ledger.csv",
    ]

    uploaded_csvs = st.file_uploader(
        "Drop CSV files here",
        type=["csv"],
        accept_multiple_files=True,
        help="Upload all 7 CSV files (see Data Dictionary). You can also generate sample data.",
        label_visibility="visible",
    )

    # Map uploaded files by filename
    uploaded_map = {f.name: f for f in (uploaded_csvs or [])}
    loaded_names = set(uploaded_map.keys()) & set(EXPECTED_CSVS)

    if uploaded_csvs:
        for name in EXPECTED_CSVS:
            icon = "✅" if name in uploaded_map else "⬜"
            st.caption(f"{icon} {name}")

    st.divider()

    # ── Business Rules Upload ─────────────────────────────────────────────────
    st.subheader("📋 Business Rules Document")
    st.caption("Upload business_rules.docx or use the one already in the project folder.")

    uploaded_rules = st.file_uploader(
        "business_rules.docx",
        type=["docx"],
        label_visibility="collapsed",
    )

    # Auto-detect rules file in project dir
    default_rules_path = ROOT / "business_rules.docx"
    if uploaded_rules:
        rules_source_label = f"Uploaded: {uploaded_rules.name}"
    elif default_rules_path.exists():
        rules_source_label = "Using project folder: business_rules.docx"
    else:
        rules_source_label = "No rules document found"

    st.caption(rules_source_label)

    st.divider()

    # ── Generate sample data ──────────────────────────────────────────────────
    st.subheader("⚙️ Sample Data")

    with st.expander("Generate synthetic CPG dataset"):
        st.caption(
            "Creates 50 SKUs · 20 retailers · 104 weeks · ~100k sales rows. "
            "Takes ~20 seconds. Saves CSVs to `data/` folder."
        )
        if st.button("Generate & Save to data/", type="secondary"):
            with st.spinner("Generating synthetic data…"):
                try:
                    from data.generate_data import (
                        generate_calendar, generate_sku_master,
                        generate_retailer_master, generate_cannibalization_matrix,
                        generate_promo_history, generate_sales_history,
                        generate_trade_spend_ledger,
                    )
                    data_dir = ROOT / "data"
                    data_dir.mkdir(exist_ok=True)

                    _cal   = generate_calendar();        _cal.to_csv(data_dir / "calendar.csv", index=False)
                    _skus  = generate_sku_master();      _skus.to_csv(data_dir / "sku_master.csv", index=False)
                    _rets  = generate_retailer_master(); _rets.to_csv(data_dir / "retailer_master.csv", index=False)
                    _can   = generate_cannibalization_matrix(_skus); _can.to_csv(data_dir / "cannibalization_matrix.csv", index=False)
                    _ph    = generate_promo_history(_skus, _rets, _cal); _ph.to_csv(data_dir / "promo_history.csv", index=False)
                    st.info("Generating sales_history (largest table)…")
                    _sh    = generate_sales_history(_skus, _rets, _cal, _ph); _sh.to_csv(data_dir / "sales_history.csv", index=False)
                    _tsl   = generate_trade_spend_ledger(_ph); _tsl.to_csv(data_dir / "trade_spend_ledger.csv", index=False)

                    st.success(f"Generated {len(_sh):,} sales rows. Reload the page then click 'Load Data'.")
                except Exception as e:
                    st.error(f"Generation failed: {e}")

    st.divider()

    # ── Load Button ───────────────────────────────────────────────────────────
    st.subheader("🚀 Load into Session")

    def _load_data():
        ds = DataStore()
        errors = []

        def _try_load(attr, name):
            # 1. Uploaded file  2. Saved in data/ dir
            if name in uploaded_map:
                try:
                    setattr(ds, attr, _read_csv(uploaded_map[name]))
                    return True
                except Exception as e:
                    errors.append(f"{name}: {e}")
            local = ROOT / "data" / name
            if local.exists():
                try:
                    setattr(ds, attr, pd.read_csv(local))
                    return True
                except Exception as e:
                    errors.append(f"{name} (local): {e}")
            return False

        _try_load("sku_master",            "sku_master.csv")
        _try_load("retailer_master",       "retailer_master.csv")
        _try_load("calendar",              "calendar.csv")
        _try_load("cannibalization_matrix","cannibalization_matrix.csv")
        _try_load("promo_history",         "promo_history.csv")
        _try_load("sales_history",         "sales_history.csv")
        _try_load("trade_spend_ledger",    "trade_spend_ledger.csv")

        st.session_state["data_store"] = ds
        st.session_state["data_loaded"] = ds.is_loaded

        # Parse rules
        if uploaded_rules:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(uploaded_rules.read())
                tmp_path = tmp.name
        elif default_rules_path.exists():
            tmp_path = str(default_rules_path)
        else:
            tmp_path = None

        if tmp_path:
            try:
                rules_store, low_conf = parse_rules_docx(tmp_path)
                st.session_state["rules_store"] = rules_store
                st.session_state["rules_loaded"] = True
                if low_conf:
                    st.warning(f"{len(low_conf)} rule(s) have low parser confidence — review flagged.")
            except Exception as e:
                errors.append(f"Rules parsing: {e}")

        return errors

    if st.button("Load Data", type="primary", use_container_width=True):
        with st.spinner("Loading…"):
            errs = _load_data()
        if errs:
            for e in errs:
                st.error(e)
        if st.session_state["data_loaded"]:
            st.success("Data loaded!", icon="✅")
        else:
            st.warning("Some files missing — see above.")

    # ── Status ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📈 Session Status")
    ds = st.session_state["data_store"]

    status_rows = [
        ("SKU Master",            ds.sku_master,            "sku_master.csv"),
        ("Retailer Master",       ds.retailer_master,       "retailer_master.csv"),
        ("Calendar",              ds.calendar,              "calendar.csv"),
        ("Sales History",         ds.sales_history,         "sales_history.csv"),
        ("Promo History",         ds.promo_history,         "promo_history.csv"),
        ("Cannibalization Matrix",ds.cannibalization_matrix,"cannibalization_matrix.csv"),
        ("Trade Spend Ledger",    ds.trade_spend_ledger,    "trade_spend_ledger.csv"),
    ]
    for label, df, _ in status_rows:
        if df is not None:
            st.caption(f"✅ {label} ({len(df):,} rows)")
        else:
            st.caption(f"⬜ {label}")

    rules_store = st.session_state["rules_store"]
    if rules_store:
        st.caption(f"✅ Business Rules ({len(rules_store)} rules)")
    else:
        st.caption("⬜ Business Rules")

    if st.session_state["scenarios_store"]:
        n = len(st.session_state["scenarios_store"])
        st.caption(f"💾 {n} scenario(s) saved this session")


# ── Main area — 3 tabs ────────────────────────────────────────────────────────
tab_plan, tab_compare, tab_rationale = st.tabs([
    "💬 Plan Builder",
    "📊 Scenario Compare",
    "🔍 Rationale",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PLAN BUILDER (chat)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_plan:
    col_chat, col_info = st.columns([3, 1], gap="medium")

    with col_info:
        st.subheader("Quick Start")
        st.markdown("""
**Example prompts:**

> *"Plan Q3-2025 promotions for BrewCo Coffee across Tier 1 retailers within a ₹30M budget"*

> *"Which promotions should I run during Diwali week for SnackRight chips?"*

> *"Improve this plan: Price Off 15% on SKU-0001 at RET-001 for 4 weeks — find a higher-ROI alternative"*

> *"Show me the compliance status of a plan with 20% discount on Premium Coffee at BigMart"*
        """)

        st.divider()
        st.subheader("Available SKUs")
        if ds.sku_master is not None:
            sku_display = ds.sku_master[["sku_id", "sku_name", "brand", "list_price"]].copy()
            sku_display["list_price"] = sku_display["list_price"].map("₹{:.0f}".format)
            st.dataframe(sku_display, height=300, use_container_width=True, hide_index=True)
        else:
            st.info("Load data to see SKU list.")

        st.subheader("Retailers")
        if ds.retailer_master is not None:
            ret_display = ds.retailer_master[["retailer_id","retailer_name","tier","channel"]].copy()
            st.dataframe(ret_display, height=220, use_container_width=True, hide_index=True)

    with col_chat:
        st.subheader("Plan Builder")

        # Render existing messages
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("trace"):
                    with st.expander(f"🔧 Tool call trace ({len(msg['trace'])} steps)", expanded=False):
                        for step in msg["trace"]:
                            if step.get("step") == "tool_call":
                                st.markdown(
                                    f'<div class="trace-step">'
                                    f'<strong>{step["tool_name"]}</strong> · '
                                    f'{step["tool_result_summary"]} · '
                                    f'{step["elapsed_sec"]}s</div>',
                                    unsafe_allow_html=True,
                                )
                            elif step.get("step") == "final_response":
                                st.caption(
                                    f"Completed in {step['elapsed_sec']}s · "
                                    f"Tokens: {step['input_tokens']} in / {step['output_tokens']} out"
                                )

        # Gate: require data and API key
        if not st.session_state["data_loaded"]:
            st.info("Load data files from the sidebar before chatting.", icon="ℹ️")
            st.stop()

        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.warning("Set your Anthropic API key in the sidebar.", icon="⚠️")
            st.stop()

        # Chat input
        user_input = st.chat_input("Describe your planning intent, ask for a plan, or refine a scenario…")

        if user_input:
            # Show user message immediately
            with st.chat_message("user"):
                st.markdown(user_input)
            st.session_state["messages"].append({"role": "user", "content": user_input, "trace": []})

            # Build history list for the API (exclude trace keys)
            history_for_api = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["messages"][:-1]  # exclude the just-added user msg
            ]

            with st.chat_message("assistant"):
                with st.spinner("Agent thinking…"):
                    reply, updated_history, trace = run_agent_turn(
                        user_message=user_input,
                        conversation_history=history_for_api,
                        data_store=st.session_state["data_store"],
                        scenarios_store=st.session_state["scenarios_store"],
                        rules_store=st.session_state["rules_store"],
                    )

                st.markdown(reply)

                if trace:
                    with st.expander(f"🔧 Tool call trace ({len(trace)} steps)", expanded=False):
                        for step in trace:
                            if step.get("step") == "tool_call":
                                st.markdown(
                                    f'<div class="trace-step">'
                                    f'<strong>{step["tool_name"]}</strong> · '
                                    f'{step["tool_result_summary"]} · '
                                    f'{step["elapsed_sec"]}s</div>',
                                    unsafe_allow_html=True,
                                )
                            elif step.get("step") == "final_response":
                                st.caption(
                                    f"Completed in {step['elapsed_sec']}s · "
                                    f"Tokens: {step['input_tokens']} in / {step['output_tokens']} out"
                                )

            st.session_state["messages"].append({"role": "assistant", "content": reply, "trace": trace})

        # Saved scenarios quick-view
        if st.session_state["scenarios_store"]:
            st.divider()
            st.caption("**Saved scenarios this session:**")
            for sid, sc in st.session_state["scenarios_store"].items():
                compliance = "✅ Compliant" if sc["is_compliant"] else f"⚠️ {len(sc['compliance_violations'])} violation(s)"
                st.caption(
                    f"`{sid}` · {sc['plan_name']} · ROI {sc['plan_roi']}x · "
                    f"₹{sc['total_brand_spend_inr']:,.0f} spend · {compliance}"
                )

        # Clear chat
        if st.session_state["messages"]:
            if st.button("Clear conversation", type="secondary"):
                st.session_state["messages"] = []
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCENARIO COMPARE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    st.subheader("Scenario Compare")

    scenarios = st.session_state["scenarios_store"]
    if not scenarios:
        st.info(
            "No scenarios yet. Use the Plan Builder to simulate plans — "
            "each `simulate_plan` call auto-saves a scenario here.",
            icon="ℹ️",
        )
    else:
        sc_options = {f"{v['plan_name']} [{sid}]": sid for sid, v in scenarios.items()}
        selected_labels = st.multiselect(
            "Select scenarios to compare (up to 4)",
            options=list(sc_options.keys()),
            max_selections=4,
            default=list(sc_options.keys())[:min(3, len(sc_options))],
        )
        selected_ids = [sc_options[l] for l in selected_labels]

        if not selected_ids:
            st.info("Select at least one scenario above.")
        else:
            selected_scenarios = [scenarios[sid] for sid in selected_ids]

            # ── Summary metrics table ─────────────────────────────────────────
            st.markdown("#### Summary Metrics")
            summary_rows = []
            for sc in selected_scenarios:
                summary_rows.append({
                    "Scenario": sc["plan_name"],
                    "Quarter": sc["quarter"],
                    "ROI": f"{sc['plan_roi']:.2f}x",
                    "Brand Spend (₹)": f"₹{sc['total_brand_spend_inr']:,.0f}",
                    "Incr. Revenue (₹)": f"₹{sc['total_incremental_revenue_inr']:,.0f}",
                    "Incr. Gross Profit (₹)": f"₹{sc['total_incremental_gp_inr']:,.0f}",
                    "# Promos": sc["num_promo_events"],
                    "Compliance": "✅ Pass" if sc["is_compliant"] else f"❌ {len(sc['compliance_violations'])} violations",
                })
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            # ── ROI bar chart ─────────────────────────────────────────────────
            st.markdown("#### ROI Comparison")
            fig_roi = go.Figure()
            colors = px.colors.qualitative.Set2
            for i, sc in enumerate(selected_scenarios):
                fig_roi.add_trace(go.Bar(
                    name=sc["plan_name"],
                    x=[sc["plan_name"]],
                    y=[sc["plan_roi"]],
                    marker_color=colors[i % len(colors)],
                    text=[f"{sc['plan_roi']:.2f}x"],
                    textposition="outside",
                ))
            fig_roi.update_layout(
                yaxis_title="Plan ROI (Incremental GP / Trade Investment)",
                showlegend=False,
                height=320,
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig_roi, use_container_width=True)

            # ── Spend vs Incremental GP waterfall ────────────────────────────
            st.markdown("#### Spend vs Incremental Gross Profit")
            fig_bar = go.Figure()
            names = [sc["plan_name"] for sc in selected_scenarios]
            spends = [sc["total_brand_spend_inr"] / 1e6 for sc in selected_scenarios]
            igps   = [sc["total_incremental_gp_inr"] / 1e6 for sc in selected_scenarios]
            fig_bar.add_trace(go.Bar(name="Brand Spend (₹M)", x=names, y=spends, marker_color="#ef5350"))
            fig_bar.add_trace(go.Bar(name="Incr. Gross Profit (₹M)", x=names, y=igps, marker_color="#42a5f5"))
            fig_bar.update_layout(
                barmode="group",
                yaxis_title="₹ Millions",
                height=320,
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            # ── Compliance detail ─────────────────────────────────────────────
            st.markdown("#### Compliance Detail")
            for sc in selected_scenarios:
                with st.expander(
                    f"{sc['plan_name']} — "
                    + ("✅ Fully compliant" if sc["is_compliant"]
                       else f"❌ {len(sc['compliance_violations'])} violation(s)"),
                    expanded=not sc["is_compliant"],
                ):
                    if sc["is_compliant"]:
                        st.success("All 17 business rules passed.")
                    else:
                        for v in sc["compliance_violations"]:
                            st.markdown(
                                f'<span class="violation-chip">{v["rule_id"]}</span> '
                                f'**{v["rule_statement"]}**  \n'
                                f'{v["detail"]}',
                                unsafe_allow_html=True,
                            )
                            st.divider()

            # ── Per-event breakdown ───────────────────────────────────────────
            st.markdown("#### Promo Event Breakdown")
            for sc in selected_scenarios:
                with st.expander(f"{sc['plan_name']} — {sc['num_promo_events']} events"):
                    rows = []
                    for ev in sc.get("events", []):
                        rows.append({
                            "Promo": ev.get("promo_id", ""),
                            "SKU": ev.get("sku_id", ""),
                            "Retailer": ev.get("retailer_id", ""),
                            "Mechanic": ev.get("mechanic", ""),
                            "Discount": f"{ev.get('discount_depth_pct', 0):.0%}",
                            "Weeks": f"{ev.get('start_week','')} → {ev.get('end_week','')}",
                            "Baseline Units": ev.get("baseline_total", ""),
                            "Incr. Units (net)": ev.get("net_incremental_units", ""),
                            "Cannibal. Loss": ev.get("cannibalization_loss", 0),
                            "ROI": f"{ev.get('roi', 0):.2f}x",
                            "Brand Spend (₹)": f"₹{ev.get('brand_trade_investment_inr', 0):,.0f}",
                        })
                    if rows:
                        df_ev = pd.DataFrame(rows)
                        st.dataframe(df_ev, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — RATIONALE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_rationale:
    st.subheader("Rationale Inspector")
    st.caption(
        "Select a scenario and a specific promo event to see the full "
        "analytical breakdown — baseline, lift model, cannibalization, ROI math, "
        "and rule audit trail."
    )

    scenarios = st.session_state["scenarios_store"]
    rules_store = st.session_state["rules_store"]

    if not scenarios:
        st.info("No scenarios yet. Simulate a plan in the Plan Builder first.", icon="ℹ️")
    else:
        sc_options = {f"{v['plan_name']} [{sid}]": sid for sid, v in scenarios.items()}
        chosen_label = st.selectbox("Select scenario", list(sc_options.keys()))
        chosen_id = sc_options[chosen_label]
        sc = scenarios[chosen_id]

        # Scenario headline
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plan ROI", f"{sc['plan_roi']:.2f}x")
        c2.metric("Brand Spend", f"₹{sc['total_brand_spend_inr']/1e6:.1f}M")
        c3.metric("Incr. Gross Profit", f"₹{sc['total_incremental_gp_inr']/1e6:.1f}M")
        c4.metric("Promo Events", sc["num_promo_events"])

        compliance_status = "✅ Fully Compliant" if sc["is_compliant"] else f"❌ {len(sc['compliance_violations'])} Violation(s)"
        if sc["is_compliant"]:
            st.success(compliance_status)
        else:
            st.error(compliance_status)

        st.divider()

        # ── Rule audit trail for this scenario ───────────────────────────────
        st.markdown("#### Business Rules Checked")
        rule_cats = {}
        for rule in rules_store:
            rule_cats.setdefault(rule["category"], []).append(rule)

        violation_ids = {v["rule_id"] for v in sc.get("compliance_violations", [])}
        cols = st.columns(3)
        for i, rule in enumerate(rules_store):
            col = cols[i % 3]
            with col:
                if rule["rule_id"] in violation_ids:
                    st.markdown(
                        f'<span class="violation-chip">❌ {rule["rule_id"]}</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<span class="pass-chip">✅ {rule["rule_id"]}</span>',
                        unsafe_allow_html=True,
                    )
                st.caption(rule["statement"][:80] + ("…" if len(rule["statement"]) > 80 else ""))

        if violation_ids:
            st.divider()
            st.markdown("#### Violation Detail")
            for v in sc["compliance_violations"]:
                with st.container(border=True):
                    st.markdown(
                        f'<span class="violation-chip">{v["rule_id"]}</span> '
                        f'**{v["rule_statement"]}**',
                        unsafe_allow_html=True,
                    )
                    st.write(v["detail"])
                    if v.get("promo_id"):
                        st.caption(f"Affected event: `{v['promo_id']}`")
                    # Show rationale from rules store
                    rule_match = next((r for r in rules_store if r["rule_id"] == v["rule_id"]), None)
                    if rule_match and rule_match.get("rationale"):
                        st.caption(f"**Rationale:** {rule_match['rationale']}")

        st.divider()

        # ── Per-event rationale ───────────────────────────────────────────────
        st.markdown("#### Promo Event Deep-Dive")
        events = sc.get("events", [])
        if not events:
            st.info("No events in this scenario.")
        else:
            event_options = {
                f"{ev.get('promo_id','?')} · {ev.get('sku_id','')} @ {ev.get('retailer_id','')}": i
                for i, ev in enumerate(events)
            }
            chosen_ev_label = st.selectbox("Select promo event", list(event_options.keys()))
            ev = events[event_options[chosen_ev_label]]

            # Look up SKU and retailer names
            sku_row = (st.session_state["data_store"].sku_master or pd.DataFrame())
            ret_row = (st.session_state["data_store"].retailer_master or pd.DataFrame())

            sku_info = sku_row[sku_row["sku_id"] == ev["sku_id"]].iloc[0].to_dict() if (
                sku_row is not None and not sku_row.empty and ev["sku_id"] in sku_row["sku_id"].values
            ) else {}
            ret_info = ret_row[ret_row["retailer_id"] == ev["retailer_id"]].iloc[0].to_dict() if (
                ret_row is not None and not ret_row.empty and ev["retailer_id"] in ret_row["retailer_id"].values
            ) else {}

            col_l, col_r = st.columns(2)

            with col_l:
                st.markdown("**Promotion Details**")
                with st.container(border=True):
                    st.write(f"**SKU:** {ev['sku_id']} — {sku_info.get('sku_name', '')}")
                    st.write(f"**Retailer:** {ev['retailer_id']} — {ret_info.get('retailer_name', '')} ({ret_info.get('tier','')})")
                    st.write(f"**Mechanic:** {ev.get('mechanic','')}")
                    st.write(f"**Discount:** {ev.get('discount_depth_pct',0):.0%}")
                    st.write(f"**Period:** {ev.get('start_week','')} → {ev.get('end_week','')}")
                    st.write(f"**List Price:** ₹{sku_info.get('list_price', 0):.2f}")
                    st.write(f"**Promo Price:** ₹{ev.get('promo_price', 0):.2f}")
                    st.write(f"**COGS/unit:** ₹{sku_info.get('cogs_per_unit', 0):.2f}")

                st.markdown("**Baseline & Lift**")
                with st.container(border=True):
                    st.write(f"**Baseline total units (promo window):** {ev.get('baseline_total', 0):,}")
                    st.write(f"**Lift %:** {ev.get('lift_pct', 0):.1%}")
                    st.write(f"**Gross incremental units:** {ev.get('incremental_units', 0):,}")
                    st.write(f"**Cannibalization loss:** {ev.get('cannibalization_loss', 0):,} units")
                    if ev.get("rule_x01_violation"):
                        st.markdown(
                            '<span class="violation-chip">⚠️ RULE-X01</span> '
                            f'Conflict with: {ev.get("rule_x01_conflict_skus",[])}',
                            unsafe_allow_html=True,
                        )
                    st.write(f"**Net incremental units:** {ev.get('net_incremental_units', 0):,}")

            with col_r:
                st.markdown("**ROI Math**")
                with st.container(border=True):
                    st.write(f"**Incremental Revenue:** ₹{ev.get('incremental_revenue_inr', 0):,.0f}")
                    st.write(f"**Incremental Gross Profit:** ₹{ev.get('incremental_gross_profit_inr', 0):,.0f}")
                    st.write(f"**Brand Trade Investment:** ₹{ev.get('brand_trade_investment_inr', 0):,.0f}")
                    roi = ev.get("roi", 0)
                    roi_color = "normal" if roi >= 1.0 else "inverse"
                    st.metric("Event ROI", f"{roi:.2f}x", delta=f"{roi - 1:.2f}x vs breakeven", delta_color=roi_color)

                st.markdown("**Applicable Rules**")
                with st.container(border=True):
                    relevant_rules = []
                    disc = ev.get("discount_depth_pct", 0)
                    mech = ev.get("mechanic", "")
                    sku_cat = sku_info.get("category", "")
                    price = sku_info.get("list_price", 0)
                    margin = sku_info.get("gross_margin_pct", 0)

                    rule_checks = {
                        "RULE-D01": (price > 400, disc <= 0.15, f"Premium SKU (₹{price:.0f}) · discount {disc:.0%}"),
                        "RULE-D02": (True, disc <= 0.30, f"Discount {disc:.0%} vs 30% cap"),
                        "RULE-D03": (True, disc >= 0.05, f"Discount {disc:.0%} vs 5% min"),
                        "RULE-M01": (mech == "BOGO", margin > 0.40, f"BOGO margin {margin:.0%} vs 40% min"),
                        "RULE-M03": (mech == "Display", True, "Display duration check"),
                        "RULE-X01": (True, not ev.get("rule_x01_violation", False), "Cannibalization cross-elasticity"),
                    }

                    for rid, (applicable, passed, note) in rule_checks.items():
                        if not applicable:
                            continue
                        icon = "✅" if passed else "❌"
                        st.markdown(
                            f'<span class="rule-chip">{icon} {rid}</span> {note}',
                            unsafe_allow_html=True,
                        )

            # ── ROI waterfall chart ───────────────────────────────────────────
            st.markdown("**ROI Waterfall**")
            invest = ev.get("brand_trade_investment_inr", 1)
            igp = ev.get("incremental_gross_profit_inr", 0)
            loss_cost = ev.get("cannibalization_loss", 0) * ev.get("promo_price", 0)

            fig_wf = go.Figure(go.Waterfall(
                orientation="v",
                measure=["absolute", "relative", "relative", "total"],
                x=["Trade Investment", "Incr. Gross Profit", "Cannibal. Loss (est.)", "Net ROI Contribution"],
                y=[-invest, igp, -loss_cost, 0],
                connector={"line": {"color": "grey"}},
                decreasing={"marker": {"color": "#ef5350"}},
                increasing={"marker": {"color": "#42a5f5"}},
                totals={"marker": {"color": "#66bb6a"}},
                text=[f"₹{abs(invest):,.0f}", f"₹{igp:,.0f}",
                      f"₹{loss_cost:,.0f}", ""],
                textposition="outside",
            ))
            fig_wf.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="₹ INR")
            st.plotly_chart(fig_wf, use_container_width=True)
