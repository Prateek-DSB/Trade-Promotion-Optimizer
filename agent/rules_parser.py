"""
Rules parser — reads business_rules.docx and returns a structured rules store.
Each rule is parsed into:
    rule_id, category, statement, predicate, rationale, confidence
Rules with confidence < 0.80 are flagged for human review at startup.
"""

import re
import docx


CATEGORY_MAP = {
    "RULE-B": "Budget",
    "RULE-D": "Discount Depth",
    "RULE-M": "Mechanic Eligibility",
    "RULE-C": "Coverage",
    "RULE-E": "SKU Eligibility",
    "RULE-X": "Cannibalization",
    "RULE-R": "Compliance",
}

# Heuristic predicates extracted from the known rules text.
# In production these would be parsed from the doc; here we pre-bake them
# and mark confidence 1.0 for rules matching our known rule IDs.
KNOWN_PREDICATES = {
    "RULE-B01": "total_spend <= 50000000",
    "RULE-B02": "0.35 <= tier1_spend_ratio <= 0.55",
    "RULE-B03": "sku_spend_ratio <= 0.12",
    "RULE-D01": "discount <= 0.15 IF list_price > 400",
    "RULE-D02": "discount <= 0.30",
    "RULE-D03": "discount >= 0.05",
    "RULE-M01": "mechanic != 'BOGO' OR gross_margin_pct > 0.40",
    "RULE-M02": "mechanic != 'Combo' OR len(distinct_subcategories) >= 2",
    "RULE-M03": "mechanic != 'Display' OR duration_weeks >= 2",
    "RULE-C01": "tier1_retailer_promo_count >= 4 per quarter",
    "RULE-C02": "festival_week_promo_sku_count >= 6",
    "RULE-C03": "promo_weeks_in_13w_window <= 10",
    "RULE-E01": "days_since_launch >= 90",
    "RULE-E02": "discontinued → mechanic == 'Price Off' AND discount <= 0.40",
    "RULE-X01": "cross_elasticity <= 0.20 OR not_simultaneous_same_retailer",
    "RULE-R01": "sku_not_in_restricted_list",
    "RULE-R02": "no_restricted_claims_in_materials",
}


def _extract_paragraphs(docx_path: str) -> list[str]:
    doc = docx.Document(docx_path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def _infer_category(rule_id: str) -> str:
    prefix = rule_id[:6]
    return CATEGORY_MAP.get(prefix, "General")


def _parse_rule_block(rule_id: str, text_block: str) -> dict:
    """
    Parse a single rule block into structured fields.
    Returns a dict with rule_id, category, statement, rationale, predicate, confidence.
    """
    # Separate statement from rationale (rationale follows "Rationale:")
    rationale = ""
    statement = text_block.strip()
    if "Rationale:" in text_block:
        parts = text_block.split("Rationale:", 1)
        statement = parts[0].strip()
        rationale = parts[1].strip()

    # Remove the rule_id prefix from statement if present
    statement = re.sub(r"^RULE-[A-Z]\d+\s*", "", statement).strip()

    predicate = KNOWN_PREDICATES.get(rule_id, "")
    # Higher confidence if we have a pre-baked predicate
    confidence = 1.0 if predicate else 0.70

    return {
        "rule_id":    rule_id,
        "category":   _infer_category(rule_id),
        "statement":  statement,
        "predicate":  predicate,
        "rationale":  rationale,
        "confidence": confidence,
        "active":     True,
    }


def parse_rules_docx(docx_path: str) -> tuple[list[dict], list[dict]]:
    """
    Parse business_rules.docx into a structured rules store.

    Returns
    -------
    (rules_store, review_required)
        rules_store     – all parsed rules as list of dicts
        review_required – rules with confidence < 0.80
    """
    paragraphs = _extract_paragraphs(docx_path)

    rule_blocks: dict[str, list[str]] = {}
    current_rule_id = None

    for para in paragraphs:
        # Match lines that start with a rule ID
        match = re.match(r"^(RULE-[A-Z]\d+)\b", para)
        if match:
            current_rule_id = match.group(1)
            rule_blocks[current_rule_id] = [para]
        elif current_rule_id and para.startswith("Rationale:"):
            rule_blocks[current_rule_id].append(para)
        elif current_rule_id:
            # Continuation of current rule
            rule_blocks[current_rule_id].append(para)

    rules_store = []
    for rule_id, lines in rule_blocks.items():
        text = " ".join(lines)
        parsed = _parse_rule_block(rule_id, text)
        rules_store.append(parsed)

    # Sort by rule_id for consistent ordering
    rules_store.sort(key=lambda r: r["rule_id"])

    review_required = [r for r in rules_store if r["confidence"] < 0.80]

    return rules_store, review_required


def get_rules_by_category(rules_store: list[dict], category: str) -> list[dict]:
    return [r for r in rules_store if r["category"] == category and r["active"]]


def get_rule_by_id(rules_store: list[dict], rule_id: str) -> dict | None:
    for r in rules_store:
        if r["rule_id"] == rule_id:
            return r
    return None


def format_rules_for_context(rules_store: list[dict]) -> str:
    """
    Render the rules store as a compact text block for inclusion in the agent system prompt.
    """
    lines = ["ACTIVE BUSINESS RULES (source: business_rules.docx v1.0)\n"]
    current_cat = None
    for r in rules_store:
        if r["category"] != current_cat:
            current_cat = r["category"]
            lines.append(f"\n{current_cat.upper()}")
        lines.append(f"  {r['rule_id']}: {r['statement']}")
        if r["rationale"]:
            lines.append(f"    Rationale: {r['rationale']}")
    return "\n".join(lines)
