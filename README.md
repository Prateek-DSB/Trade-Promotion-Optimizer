# Trade Promotion ROI Optimizer

A Streamlit co-pilot for CPG Trade Marketing Managers that uses an Anthropic Claude-powered agentic loop to build, simulate, and compare quarterly promotional plans — maximising incremental ROI while enforcing business rules.

---

## Features

- **AI Plan Builder** — conversational chat interface where you describe your promotional goals and the agent builds a compliant plan, citing every business rule it consulted.
- **Scenario Compare** — side-by-side comparison of up to three promotional plans across ROI, trade spend, incremental revenue, and compliance status.
- **Agent Rationale Trace** — full step-by-step tool-call trace showing exactly how the agent arrived at each recommendation.
- **Business Rule Enforcement** — upload a `.docx` rules file; the agent parses it and automatically checks every plan for violations before presenting results.

## How the Agent Works

The agent follows a mandatory workflow on every planning request:

1. `get_applicable_rules` — retrieves relevant business rules before proposing anything
2. `get_baseline_forecast` — pulls prior-year baseline for each SKU × retailer
3. `estimate_promo_lift` — runs the price-elasticity lift model for each candidate event
4. `simulate_plan` — calculates ROI, applies cannibalization adjustments, and runs compliance check
5. If violations exist, iterates until the plan is compliant
6. Presents the final plan with ROI, spend, rule citations, and plain-English rationale

ROI is calculated using the CPG industry standard:

```
Incremental GP  = net_incremental_units × (promo_price − COGS)
Trade Investment = total_promo_units × discount_per_unit × (1 − coop_funding_pct)
ROI             = Incremental GP / Trade Investment
```

## Project Structure

```
├── app.py                  # Streamlit UI (Plan Builder, Scenario Compare, Rationale)
├── agent/
│   ├── agent_loop.py       # Claude tool-use loop (claude-sonnet-4-6, temp=0)
│   ├── tools.py            # Five agent tools + Claude tool definitions
│   └── rules_parser.py     # Parses business rules from .docx files
├── analytics/
│   ├── roi_calculator.py   # CPG-standard ROI calculation
│   ├── lift_model.py       # Price-elasticity lift model
│   ├── cannibalization.py  # Cross-SKU cannibalization adjustment
│   └── compliance_check.py # Business rule compliance engine
├── data/
│   └── generate_data.py    # Synthetic data generator for dev/demo
├── requirements.txt
└── business_rules.docx     # Default business rules file
```

## Getting Started

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### Installation

```bash
git clone https://github.com/Prateek-DSB/Trade-Promotion-Optimizer.git
cd Trade-Promotion-Optimizer
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create `.streamlit/secrets.toml` (never committed — already in `.gitignore`):

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Or set the environment variable directly:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # macOS/Linux
$env:ANTHROPIC_API_KEY="sk-ant-..."     # PowerShell
```

### Generate Sample Data

```bash
python data/generate_data.py
```

This creates synthetic SKU master, retailer master, sales history, promo history, and cannibalization matrix CSVs in the `data/` directory.

### Run the App

```bash
streamlit run app.py
```

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| AI Agent | Anthropic Claude (`claude-sonnet-4-6`) via tool use |
| Analytics | pandas, NumPy |
| Visualisation | Plotly |
| Rules Parsing | python-docx |
