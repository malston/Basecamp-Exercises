#!/usr/bin/env python3
"""ClauseScan terminal runner -- measure, tune and defend the Inference Optimization sprint.

Use this instead of running the whole notebook when you want to re-run ONE configuration,
repeat it for variance, or score it on the holdout, without re-paying for the v0 baseline.

  python3 run_clausescan.py baseline                  # run v0 once, save results/baseline.json
  python3 run_clausescan.py run --single-pass --cache --routine-model sonnet --effort low
  python3 run_clausescan.py run <levers> --repeats 5  # variance: is the result stable?
  python3 run_clausescan.py run <levers> --holdout    # frozen config on unseen contracts
  python3 run_clausescan.py latency-probe <levers>    # p50 on contracts ~8x longer
  python3 run_clausescan.py slide                     # steering-committee table from latest run

Credentials: ANTHROPIC_API_KEY from the environment, else from the nearest .env above this file.
Every run appends one JSON line to results/runs.jsonl, so nothing measured is lost.

Contracts, gold labels, playbook, schemas and grader below the marker are verbatim from
Inference_Optimization.py (the workshop source); pricing is verified against the pricing page.
"""
import argparse
import json
import pathlib
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from stress_set import STRESS_CONTRACTS, STRESS_GOLD

HERE = pathlib.Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
BASELINE_FILE = RESULTS_DIR / "baseline.json"
RUNS_FILE = RESULTS_DIR / "runs.jsonl"

MODEL_HAIKU = "claude-haiku-4-5"
MODEL_SONNET = "claude-sonnet-5"
MODEL_OPUS = "claude-opus-4-8"
ALIASES = {"haiku": MODEL_HAIKU, "sonnet": MODEL_SONNET, "opus": MODEL_OPUS}

# $/MTok, verified 2026-10-23 against https://platform.claude.com/docs/en/about-claude/pricing
# (the workshop file lists Sonnet 5 at $3/$15; the pricing page says $2/$10).
PRICING = {
    MODEL_HAIKU: {"input": 1.00, "output": 5.00},
    MODEL_SONNET: {"input": 2.00, "output": 10.00},
    MODEL_OPUS: {"input": 5.00, "output": 25.00},
}
CACHE_WRITE_MULT = 1.25   # 5-minute TTL
CACHE_READ_MULT = 0.10
BATCH_DISCOUNT = 0.50

# ── Workshop data and grader (verbatim from Inference_Optimization.py) ──────

CONTRACTS = [
    {
        "id": "C-101", "vendor": "NorthWind Logistics GmbH",
        "text": """MASTER SERVICES AGREEMENT — NorthWind Logistics GmbH ("Supplier") and Volta Industrial Group ("Customer").

1. SERVICES. Supplier provides freight forwarding and warehouse management services per attached SOWs.
2. TERM AND RENEWAL. Initial term of twenty-four (24) months. This Agreement automatically renews for successive twelve (12) month periods unless either party gives written notice of non-renewal at least sixty (60) days before the end of the then-current term.
3. FEES AND PAYMENT. Fees per Schedule A. Invoices payable net forty-five (45) days. Late amounts accrue interest at 1% per month.
4. LIMITATION OF LIABILITY. EXCEPT FOR BREACHES OF CONFIDENTIALITY, EACH PARTY'S AGGREGATE LIABILITY ARISING OUT OF THIS AGREEMENT SHALL NOT EXCEED TWO HUNDRED FIFTY THOUSAND U.S. DOLLARS ($250,000).
5. ASSIGNMENT. Either party may assign this Agreement to an affiliate or in connection with a merger or sale of substantially all assets without the consent of the other party, upon written notice.
6. CONFIDENTIALITY. Standard mutual obligations for 3 years post-termination.
7. GOVERNING LAW. This Agreement is governed by the laws of the State of Delaware, without regard to conflicts of law principles.""",
    },
    {
        "id": "C-102", "vendor": "Apex Facilities Co.",
        "text": """FACILITIES MAINTENANCE AGREEMENT — Apex Facilities Co. ("Contractor") and Volta Industrial Group ("Client").

1. SCOPE. HVAC, electrical, and janitorial maintenance for the sites listed in Exhibit 1.
2. TERM. Fixed term of thirty-six (36) months from the Effective Date. This Agreement expires at the end of the term and does not renew automatically; any extension requires a written amendment signed by both parties.
3. PRICING. Monthly fixed fee of $18,400 plus materials at cost +10%.
4. LIMITATION OF LIABILITY. Contractor's total cumulative liability under this Agreement shall not exceed ONE HUNDRED THOUSAND U.S. DOLLARS ($100,000). Neither party is liable for indirect or consequential damages.
5. ASSIGNMENT. Either party may freely assign this Agreement, including in connection with any change of control, without consent.
6. INSURANCE. Contractor maintains commercial general liability coverage of $2,000,000 per occurrence.
7. GOVERNING LAW. The laws of the State of New York govern this Agreement.""",
    },
    {
        "id": "C-103", "vendor": "Cobalt Data Services Ltd.",
        "text": """DATA PROCESSING AND HOSTING AGREEMENT — Cobalt Data Services Ltd. ("Provider") and Volta Industrial Group ("Company").

1. SERVICES. Provider hosts Company's plant telemetry platform and processes operational data.
2. TERM AND RENEWAL. Initial term of twelve (12) months, automatically renewing for successive one-year terms unless either party provides ninety (90) days' written notice of termination.
3. SERVICE LEVELS. 99.9% monthly uptime; service credits per Schedule 2.
4. LIMITATION OF LIABILITY. PROVIDER'S AGGREGATE LIABILITY SHALL NOT EXCEED FIVE HUNDRED THOUSAND U.S. DOLLARS ($500,000) OR THE FEES PAID IN THE PRIOR 12 MONTHS, WHICHEVER IS GREATER, PROVIDED THE CAP SHALL IN NO EVENT EXCEED $500,000.
5. ASSIGNMENT AND CHANGE OF CONTROL. Neither party may assign this Agreement, whether by operation of law, change of control, merger, or otherwise, without the prior written consent of the other party, such consent not to be unreasonably withheld.
6. DATA PROTECTION. Provider processes personal data per the DPA in Exhibit C.
7. GOVERNING LAW. This Agreement is governed by the laws of the State of California.""",
    },
    {
        "id": "C-104", "vendor": "Ironclad Security Services plc",
        "text": """SECURITY SERVICES AGREEMENT — Ironclad Security Services plc ("Ironclad") and Volta Industrial Group ("Principal").

1. SERVICES. Manned guarding, alarm response, and access control for Principal's UK sites.
2. TERM. Twelve (12) months from the Commencement Date, terminating automatically at expiry. Renewal only by mutual written agreement.
3. INDEMNITY. Ironclad indemnifies Principal against third-party claims arising from Ironclad's negligence; Principal indemnifies Ironclad against claims arising from site conditions not disclosed in the Site Survey. Each indemnity is uncapped and survives termination for six (6) years.
4. LIABILITY. The parties acknowledge the indemnities in Section 3. This Agreement does not otherwise state any cap, ceiling, or other limitation on either party's liability.
5. ASSIGNMENT AND CHANGE OF CONTROL. Ironclad may terminate this Agreement on thirty (30) days' notice upon any change of control of Principal. Any assignment by either party requires the prior written consent of the other.
6. TUPE. The parties acknowledge the potential application of TUPE regulations to guard personnel on expiry.
7. GOVERNING LAW. This Agreement and any dispute arising out of it are governed by the laws of England and Wales.""",
    },
    {
        "id": "C-105", "vendor": "Helios Components S.A.",
        "text": """SUPPLY AGREEMENT — Helios Components S.A. ("Helios") and Volta Industrial Group ("Buyer").

1. SUPPLY. Helios supplies the precision components listed in Annex 1 per Buyer's purchase orders.
2. TERM AND RENEWAL. Initial term of twenty-four (24) months, automatically extending for successive twelve-month periods unless either party gives one hundred twenty (120) days' notice.
3. PRICING. Annex 2 price list, adjusted annually per the PPI index, capped at 4% per year.
4. LIMITATION OF LIABILITY. Subject to Section 9 (IP Indemnity), each party's aggregate liability under this Agreement shall not exceed ONE MILLION U.S. DOLLARS ($1,000,000).
5. ASSIGNMENT AND CHANGE OF CONTROL. Any direct or indirect change of control of Buyer requires Helios's prior written consent. Helios may withhold consent in its sole discretion.
6. QUALITY. Components conform to the specifications in Annex 3; non-conforming lots replaced at Helios's cost.
7. GOVERNING LAW. This Agreement is governed by the laws of the State of Texas.

AMENDMENT NO. 2 (executed and effective). The parties agree as follows: Section 4 (Limitation of Liability) of the Agreement is deleted in its entirety and shall be of no further force or effect. For the avoidance of doubt, following this Amendment the Agreement states no cap on either party's liability. All other terms remain unchanged.""",
    },
    {
        "id": "C-106", "vendor": "Brightline Staffing LLC",
        "text": """STAFFING SERVICES AGREEMENT — Brightline Staffing LLC ("Brightline") and Volta Industrial Group ("Client").

1. SERVICES. Brightline supplies temporary production and warehouse personnel on request.
2. TERM AND RENEWAL. One (1) year initial term, renewing automatically for successive one-year terms unless either party gives thirty (30) days' written notice prior to renewal.
3. RATES. Bill rates per Rate Card v7; overtime at 1.5×; conversion fee of 20% of first-year salary for direct hires within 12 months.
4. WORKER CLASSIFICATION. Brightline is the employer of record and is responsible for wages, withholding, and workers' compensation coverage.
5. ASSIGNMENT. Either party may assign this Agreement without the other party's consent, including in connection with a change of control, provided the assignee assumes all obligations.
6. WARRANTIES. Services performed in a professional and workmanlike manner. THE PARTIES HAVE NOT AGREED ANY LIMITATION OR CAP ON LIABILITY UNDER THIS AGREEMENT.
7. GOVERNING LAW. This Agreement is governed by the laws of the State of Illinois.""",
    },
]

GOLD = {
    "C-101": {"auto_renewal": True,  "change_of_control": False, "liability_cap_usd": 250000,
              "governing_law": "Delaware",          "risk_tier": "LOW"},
    "C-102": {"auto_renewal": False, "change_of_control": False, "liability_cap_usd": 100000,
              "governing_law": "New York",          "risk_tier": "LOW"},
    "C-103": {"auto_renewal": True,  "change_of_control": True,  "liability_cap_usd": 500000,
              "governing_law": "California",        "risk_tier": "MEDIUM"},
    "C-104": {"auto_renewal": False, "change_of_control": True,  "liability_cap_usd": None,
              "governing_law": "England and Wales", "risk_tier": "HIGH"},
    "C-105": {"auto_renewal": True,  "change_of_control": True,  "liability_cap_usd": None,
              "governing_law": "Texas",             "risk_tier": "HIGH"},
    "C-106": {"auto_renewal": True,  "change_of_control": False, "liability_cap_usd": None,
              "governing_law": "Illinois",          "risk_tier": "MEDIUM"},
}

PLAYBOOK_CORE = """You are ClauseScan, the contract-diligence reviewer for Project HELVETICA \
(Aldgate Capital Partners' acquisition of Volta Industrial Group). You review supplier \
contracts and report five audited fields. Work only from the contract text provided. Never \
guess: if the contract is silent on a point, report it as absent rather than inventing terms.

## Audited fields
1. auto_renewal (boolean) — true only if the contract renews automatically absent notice. A \
fixed term that expires, or renewal "by mutual written agreement", is NOT auto-renewal.
2. change_of_control (boolean) — true if assignment or change of control of either party \
requires the counterparty's prior consent, or gives the counterparty a termination right. \
Free assignment or notice-only assignment is false.
3. liability_cap_usd (number or null) — the aggregate liability cap in USD. null if no cap is \
stated, if liability is expressly uncapped, or if an amendment removed the cap. Amendments \
override the original clause — always check for amendments before reporting.
4. governing_law (string) — the governing jurisdiction, e.g. "Delaware" or "England and Wales".
5. risk_tier (LOW | MEDIUM | HIGH) — apply this rule exactly:
   HIGH = change-of-control consent/termination right present AND no liability cap.
   MEDIUM = exactly one of those two red flags present.
   LOW = neither red flag (no change-of-control restriction AND a cap is stated).

## Review discipline
- Read every section, then re-check the two red-flag clauses before concluding.
- Quote-check: the evidence you cite must appear in the contract.
- Deal context: Aldgate's purchase will itself trigger change-of-control clauses across the \
estate — that is why the field is audited.
"""

# The clause library and precedent notes make the playbook realistically long. On a real
# engagement this is the 40-page standards PDF your firm maintains.
CLAUSE_LIBRARY = [
    ("Automatic renewal (evergreen)", "Term continues for successive periods unless a party gives notice by a stated deadline. Capture the notice window and the renewal period length.", "Notice windows under 30 days are operationally dangerous during an integration."),
    ("Fixed term with mutual-agreement renewal", "Agreement expires at the end of the stated term; any continuation needs a signed amendment.", "Often misread as auto-renewal. It is not."),
    ("Assignment with consent", "Neither party may assign without prior written consent; usually includes 'by operation of law' and merger language.", "This is a change-of-control restriction even when the words 'change of control' never appear."),
    ("Free assignment", "Either party may assign to affiliates or acquirers, sometimes with notice only.", "Notice-only assignment is NOT a change-of-control restriction."),
    ("Change-of-control termination right", "Counterparty may terminate upon a change of control of the other party.", "A termination right is as dangerous to deal value as a consent right — treat it as change_of_control = true."),
    ("Aggregate liability cap", "A single dollar ceiling on total liability under the agreement.", "Check whether carve-outs (confidentiality, IP, indemnity) sit outside the cap."),
    ("Capped at fees paid", "Liability limited to fees paid over a trailing window, sometimes with a dollar ceiling on top.", "Report the effective ceiling where one is stated; otherwise treat as a cap of unstated amount."),
    ("Uncapped liability", "No limitation-of-liability clause, or an express statement that liability is unlimited.", "Silence is a red flag, not a default. Report null."),
    ("Amendment overriding liability terms", "Later amendments may delete or rewrite the limitation-of-liability section.", "The amendment controls. Re-read amendments before reporting any cap."),
    ("Mutual indemnity, uncapped", "Each party indemnifies the other for defined claim classes with no ceiling.", "Uncapped indemnities alongside a deleted cap compound exposure."),
    ("Governing law", "The jurisdiction whose law governs the contract.", "Distinguish governing law from venue/forum; report the law."),
    ("Service levels and credits", "Uptime or performance commitments with credit remedies.", "Credits are usually the exclusive remedy — note but do not audit."),
    ("Payment terms", "Net-day windows, late interest, price-adjustment indices.", "Index-linked price escalators matter for the operating model, not this audit."),
    ("Confidentiality", "Mutual non-disclosure obligations with survival periods.", "Often carved out of the liability cap."),
    ("Insurance requirements", "Required coverage types and limits.", "Insurance limits are not liability caps. Do not conflate."),
    ("TUPE / employee transfer", "EU/UK staff-transfer regulations on outsourcing changes.", "Integration planning input; not an audited field."),
    ("Exclusivity", "Sole-supplier or minimum-purchase commitments.", "Flag in evidence notes if material; not an audited field."),
    ("Termination for convenience", "Either party may exit on notice without cause.", "Shortens effective exposure; note the notice window."),
    ("Most-favored-customer pricing", "Supplier promises pricing no worse than comparable customers.", "Diligence interest for procurement, not this audit."),
    ("IP indemnity", "Supplier defends infringement claims; sometimes uncapped.", "Carve-outs can sit outside the cap — read the cap clause's 'subject to' language."),
    ("Force majeure", "Excused performance on defined events.", "Not audited."),
    ("Audit rights", "Customer may audit supplier records or facilities.", "Not audited here; useful for integration."),
]

PRECEDENT_NOTES = [
    "Volta's 2024 acquisition of Kessler Tooling stalled five weeks on unflagged change-of-control consents across 1,100 supplier contracts.",
    "Aldgate's deal team treats any uncapped-liability supplier with consent rights as a Day-1 escalation.",
    "Notice windows: the integration office needs 90+ days of runway; sub-30-day windows go on the watch list.",
    "Caps stated in non-USD currencies are converted at the deal-model rate; report the stated figure and flag the currency in evidence.",
    "Where an MSA and SOW conflict, the MSA controls unless the SOW says otherwise — playbook v7, §3.2.",
    "Indemnity carve-outs outside the cap do not change liability_cap_usd; they belong in evidence.",
    "A termination-on-change-of-control right is reported as change_of_control = true even absent a consent requirement.",
    "Renewal 'by mutual written agreement' is not auto-renewal; the deal model treats those contracts as expiring.",
    "If two clauses conflict and no amendment resolves them, report the more conservative reading and say so in evidence.",
    "Evidence must cite section numbers; reviewers spot-check 10% of output against source text.",
]

WORKED_EXAMPLES = """
## Worked examples
Example A: a contract with free assignment and a $400,000 aggregate cap → change_of_control \
false, liability_cap_usd 400000, risk_tier LOW.
Example B: a contract requiring consent for change of control with a $1M cap → \
change_of_control true, cap 1000000, exactly one red flag → risk_tier MEDIUM.
Example C: a contract with a consent requirement whose cap was deleted by amendment → \
change_of_control true, liability_cap_usd null, both red flags → risk_tier HIGH.
"""


def _build_playbook() -> str:
    parts = [PLAYBOOK_CORE, "\n## Clause library\n"]
    for name, definition, red_flag in CLAUSE_LIBRARY:
        parts.append(f"### {name}\n{definition}\nRed flag note: {red_flag}\n")
    parts.append("\n## Negotiation precedent notes\n")
    for note in PRECEDENT_NOTES:
        parts.append(f"- {note}")
    parts.append(WORKED_EXAMPLES)
    text = "\n".join(parts)
    # Pad deterministically past the largest minimum cacheable prefix (4096 tokens on
    # Opus/Haiku; ~4 chars per token) so the caching lever works on every model.
    annex = "\n\n## Annex: clause library (deal-team annotated re-issue)\n" + "\n".join(
        f"### {n}\n{d}\nRed flag note: {r}\n" for n, d, r in CLAUSE_LIBRARY)
    while len(text) < 22000:
        text += annex
    return text


PLAYBOOK = _build_playbook()

def _normalize_cap(value):
    """Coerce model output for liability_cap_usd into a float or None."""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower().replace("$", "").replace(",", "")
        if v in ("", "none", "null", "n/a", "uncapped", "no cap"):
            return None
        try:
            return float(v)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def grade_fields(fields: dict, gold: dict) -> dict:
    """Per-field pass/fail for one contract."""
    f = fields or {}
    checks = {}
    checks["auto_renewal"] = bool(f.get("auto_renewal")) == gold["auto_renewal"]
    checks["change_of_control"] = bool(f.get("change_of_control")) == gold["change_of_control"]
    cap = _normalize_cap(f.get("liability_cap_usd"))
    if gold["liability_cap_usd"] is None:
        checks["liability_cap_usd"] = cap is None
    else:
        checks["liability_cap_usd"] = cap is not None and abs(cap - gold["liability_cap_usd"]) < 1
    gl, gg = str(f.get("governing_law") or "").lower(), gold["governing_law"].lower()
    checks["governing_law"] = bool(gl) and (gg in gl or gl in gg)
    checks["risk_tier"] = str(f.get("risk_tier") or "").strip().upper() == gold["risk_tier"]
    return checks


def extract_json(text: str):
    """Pull the first valid JSON object out of free text (v0 needs this; v1 may not)."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    for start, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        break
    return None

EXTRACT_INSTRUCTION = (
    "Determine the five audited fields for the contract below. Respond with a JSON object "
    "with keys auto_renewal, change_of_control, liability_cap_usd, governing_law, risk_tier, "
    "evidence.\n\nCONTRACT:\n"
)

TRIAGE_SYSTEM = (
    "You triage supplier contracts for a diligence pipeline. Classify the contract as "
    "COMPLEX if it contains any of: an amendment that modifies earlier terms, clauses that "
    "conflict with each other, unusual or uncapped indemnities, or liability terms that are "
    "ambiguous or implied rather than stated. Otherwise classify it as ROUTINE."
)

TRIAGE_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "complexity": {"type": "string", "enum": ["ROUTINE", "COMPLEX"]},
            "reason": {"type": "string", "description": "One short sentence."},
        },
        "required": ["complexity", "reason"],
        "additionalProperties": False,
    },
}

EXTRACTION_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "auto_renewal": {"type": "boolean",
                             "description": "True only if the contract renews automatically absent notice."},
            "change_of_control": {"type": "boolean",
                                  "description": "True if assignment/change of control requires consent or grants a termination right."},
            "liability_cap_usd": {"anyOf": [{"type": "number"}, {"type": "null"}],
                                  "description": "Aggregate cap in USD. null if no cap is stated or an amendment removed it."},
            "governing_law": {"type": "string",
                              "description": "Jurisdiction, e.g. 'Delaware' or 'England and Wales'."},
            "risk_tier": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"],
                          "description": "HIGH = change-of-control restriction AND no cap. MEDIUM = exactly one red flag. LOW = neither."},
            "evidence": {"type": "string",
                         "description": "One sentence citing the section numbers relied on."},
        },
        "required": ["auto_renewal", "change_of_control", "liability_cap_usd",
                     "governing_law", "risk_tier", "evidence"],
        "additionalProperties": False,
    },
}

HOLDOUT_CONTRACTS = [
    {
        "id": "C-201", "vendor": "Vanta Marketing Collective",
        "text": """MARKETING SERVICES AGREEMENT — Vanta Marketing Collective ("Agency") and Volta Industrial Group ("Client").

1. SERVICES. Brand, digital, and trade-show marketing services per approved statements of work.
2. TERM. Eighteen (18) months from the Effective Date, expiring automatically at the end of the term. Any renewal requires a new agreement executed by both parties.
3. FEES. Monthly retainer of $22,000 plus pre-approved pass-through costs.
4. LIMITATION OF LIABILITY. EACH PARTY'S TOTAL AGGREGATE LIABILITY UNDER THIS AGREEMENT IS LIMITED TO SEVENTY-FIVE THOUSAND U.S. DOLLARS ($75,000), EXCLUDING ONLY AMOUNTS PAYABLE UNDER SECTION 5 (INDEMNIFICATION FOR IP CLAIMS).
5. INDEMNIFICATION. Agency indemnifies Client against third-party IP claims arising from Agency-created materials.
6. ASSIGNMENT. Either party may assign this Agreement without consent upon written notice, including in connection with a change of control.
7. GOVERNING LAW. This Agreement is governed by the laws of the Province of Ontario, Canada.""",
    },
    {
        "id": "C-202", "vendor": "Quarry Industrial Supply Pte. Ltd.",
        "text": """INDUSTRIAL SUPPLY AGREEMENT — Quarry Industrial Supply Pte. Ltd. ("Quarry") and Volta Industrial Group ("Purchaser").

1. SUPPLY. Quarry supplies abrasives, fasteners, and consumables per released purchase orders.
2. TERM AND RENEWAL. Two (2) year initial term, automatically renewing for successive one-year terms unless either party gives ninety (90) days' written notice of non-renewal.
3. PRICING. Per the Annex A price file; freight prepaid for orders over S$5,000.
4. LIMITATION OF LIABILITY. QUARRY'S AND PURCHASER'S RESPECTIVE AGGREGATE LIABILITY ARISING OUT OF OR RELATING TO THIS AGREEMENT SHALL NOT EXCEED TWO MILLION U.S. DOLLARS ($2,000,000) IN THE AGGREGATE.
5. ASSIGNMENT AND CHANGE OF CONTROL. Neither party may assign or transfer this Agreement, including by merger, acquisition, or change of control, without the prior written consent of the other party. Any purported assignment without consent is void.
6. COMPLIANCE. Each party complies with applicable export-control and anti-corruption laws.
7. GOVERNING LAW. This Agreement is governed by the laws of Singapore.""",
    },
]

HOLDOUT_GOLD = {
    "C-201": {"auto_renewal": False, "change_of_control": False, "liability_cap_usd": 75000,
              "governing_law": "Ontario",   "risk_tier": "LOW"},
    "C-202": {"auto_renewal": True,  "change_of_control": True,  "liability_cap_usd": 2000000,
              "governing_law": "Singapore", "risk_tier": "MEDIUM"},
}


# ── Cost ────────────────────────────────────────────────────────────────────
def usage_tokens(usage) -> dict:
    """Token counts from an API usage object, as a plain dict."""
    return {"in": usage.input_tokens,
            "cw": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cr": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "out": usage.output_tokens}


def cost_of(model: str, t: dict, batch: bool = False) -> float:
    """Dollars for one call's token counts, all four terms (input, write, read, output)."""
    p = PRICING[model]
    dollars = (t["in"] * p["input"] + t["cw"] * p["input"] * CACHE_WRITE_MULT
               + t["cr"] * p["input"] * CACHE_READ_MULT + t["out"] * p["output"]) / 1e6
    return dollars * BATCH_DISCOUNT if batch else dollars


def production_cost(row_tokens: dict, contract_tokens: dict, scale: float, batch: bool = False) -> float:
    """Cost of one contract that is `scale`x longer. Only the contract text grows; the cached
    playbook and the fixed-size JSON output do not. row_tokens: {model: {calls, in, cw, cr, out}};
    contract_tokens: {model: tokens in the contract text under that model's tokenizer}."""
    total = 0.0
    for model, t in row_tokens.items():
        total += cost_of(model, t, batch)
        extra = t["calls"] * contract_tokens[model] * (scale - 1) * PRICING[model]["input"] / 1e6
        total += extra * (BATCH_DISCOUNT if batch else 1)
    return total


# ── Scoring ─────────────────────────────────────────────────────────────────
def summarize_rows(rows: list) -> dict:
    total_fields = sum(r["n_fields"] for r in rows)
    return {
        "accuracy": sum(r["n_correct"] for r in rows) / total_fields,
        "p50_s": statistics.median(r["elapsed"] for r in rows),
        "cost_per_contract": sum(r["cost"] for r in rows) / len(rows),
    }


def engagement_score(report: dict, baseline: dict) -> int:
    """The leaderboard formula: zero below the 90% accuracy gate, 100 at baseline."""
    if report["accuracy"] < 0.90:
        return 0
    return round(50 * baseline["cost_per_contract"] / max(report["cost_per_contract"], 1e-9)
                 + 50 * baseline["p50_s"] / max(report["p50_s"], 1e-9))


# ── Pipelines ───────────────────────────────────────────────────────────────
_client = None


def get_client():
    """Anthropic client, built on first use so importing this file needs no key."""
    global _client
    if _client is None:
        import anthropic
        key = _find_api_key()
        _client = anthropic.Anthropic(api_key=key, timeout=900.0, max_retries=2)
    return _client


def _find_api_key() -> str:
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key.startswith("sk-ant-"):
        return key
    for d in [HERE, *HERE.parents]:
        env = d / ".env"
        if env.is_file():
            for line in env.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val.startswith("sk-ant-"):
                        return val
    sys.exit("No Anthropic API key. Set ANTHROPIC_API_KEY or put it in a .env file (see SETUP.md).")


def text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text")


CACHED_SYSTEM = [{"type": "text", "text": PLAYBOOK, "cache_control": {"type": "ephemeral"}}]


def new_calls() -> dict:
    return {}


def record(calls: dict, model: str, usage) -> None:
    t = usage_tokens(usage)
    agg = calls.setdefault(model, {"calls": 0, "in": 0, "cw": 0, "cr": 0, "out": 0})
    agg["calls"] += 1
    for k in ("in", "cw", "cr", "out"):
        agg[k] += t[k]


def clausescan_v0(contract: dict) -> dict:
    """The inherited pipeline: two serial Opus calls, uncached playbook, essay output."""
    return two_pass(contract, MODEL_OPUS, PLAYBOOK, 8000, new_calls(), time.perf_counter())


def triage(contract: dict, calls: dict) -> str:
    resp = get_client().messages.create(
        model=MODEL_HAIKU, max_tokens=150, system=TRIAGE_SYSTEM,
        messages=[{"role": "user", "content": contract["text"]}],
        output_config={"format": TRIAGE_SCHEMA})
    record(calls, MODEL_HAIKU, resp.usage)
    return (extract_json(text_of(resp)) or {}).get("complexity", "COMPLEX")  # unknown -> COMPLEX


def derive_risk_tier(fields):
    """Apply the playbook's exact risk rule to the extracted flags: HIGH = change-of-control
    restriction AND no cap, MEDIUM = exactly one, LOW = neither. Returns a copy."""
    if not fields or "change_of_control" not in fields or "liability_cap_usd" not in fields:
        return fields
    flags = int(bool(fields["change_of_control"])) + int(fields["liability_cap_usd"] is None)
    return {**fields, "risk_tier": {0: "LOW", 1: "MEDIUM", 2: "HIGH"}[flags]}


def effort_for(cfg: dict, model: str):
    """The effort dial errors on Haiku 4.5, so it is dropped there."""
    return cfg["effort"] if cfg["effort"] and model != MODEL_HAIKU else None


def clausescan_v1(contract: dict, cfg: dict) -> dict:
    """Configurable pipeline: optional triage routing, cached playbook, one schema pass."""
    c, t0, calls = get_client(), time.perf_counter(), new_calls()
    model = cfg["routine_model"]
    if cfg["triage"]:
        verdict = triage(contract, calls)
        model = cfg["complex_model"] if verdict == "COMPLEX" else cfg["routine_model"]
    system = CACHED_SYSTEM if cfg["cache"] else PLAYBOOK
    if cfg["single_pass"]:
        output_config = {"format": EXTRACTION_SCHEMA}
        if effort_for(cfg, model):
            output_config["effort"] = effort_for(cfg, model)
        resp = c.messages.create(
            model=model, max_tokens=cfg["max_tokens"], system=system,
            messages=[{"role": "user", "content": EXTRACT_INSTRUCTION + contract["text"]}],
            output_config=output_config)
        record(calls, model, resp.usage)
        fields = extract_json(text_of(resp))
        if cfg["derive_tier"]:
            fields = derive_risk_tier(fields)
    else:
        return two_pass(contract, model, system, cfg["max_tokens"], calls, t0)
    return {"fields": fields, "calls": calls, "elapsed": time.perf_counter() - t0}


def two_pass(contract, model, system, max_tokens, calls, t0) -> dict:
    """v0's flow: briefing call, then an essay-plus-JSON call. Used for v0 and when single-pass is off."""
    c = get_client()
    r1 = c.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content":
                   "Write a detailed clause-by-clause briefing of this contract, with "
                   "commentary on anything unusual, before any extraction is attempted.\n\n"
                   + contract["text"]}])
    record(calls, model, r1.usage)
    r2 = c.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content":
                   "Here is an internal briefing of a contract:\n\n" + text_of(r1)
                   + "\n\nNow, explain your reasoning step by step in detail, and then output "
                   + "a JSON object with keys auto_renewal, change_of_control, "
                   + "liability_cap_usd, governing_law, risk_tier, evidence.\n\nCONTRACT:\n"
                   + contract["text"]}])
    record(calls, model, r2.usage)
    return {"fields": extract_json(text_of(r2)), "calls": calls, "elapsed": time.perf_counter() - t0}


# ── Portfolio runner ────────────────────────────────────────────────────────
def run_portfolio(pipeline, contracts, gold, workers: int = 0, warm_first: bool = True) -> dict:
    """Run a pipeline over contracts; grade, time and price each. With workers, the first
    contract runs alone so the cache is written before the fan-out."""

    def run_one(contract):
        out = pipeline(contract)
        checks = grade_fields(out["fields"], gold[contract["id"]])
        return {"id": contract["id"], "fields": out["fields"], "checks": checks,
                "n_correct": sum(checks.values()), "n_fields": len(checks),
                "elapsed": out["elapsed"], "tokens": out["calls"],
                "cost": sum(cost_of(m, t) for m, t in out["calls"].items())}

    wall0 = time.perf_counter()
    if workers and len(contracts) > 1:
        rows = []
        remaining = contracts
        if warm_first:
            rows.append(run_one(contracts[0]))
            remaining = contracts[1:]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            rows.extend(ex.map(run_one, remaining))
    else:
        rows = [run_one(c) for c in contracts]
    return {"rows": rows, "wall_s": time.perf_counter() - wall0, **summarize_rows(rows)}


def print_report(report: dict, label: str) -> None:
    print(f"\n-- {label} " + "-" * max(1, 64 - len(label)))
    print(f"{'ID':7}{'fields':8}{'TTC':>8}{'cost':>10}  failed checks")
    for r in report["rows"]:
        failed = ",".join(k for k, ok in r["checks"].items() if not ok) or "-"
        print(f"{r['id']:7}{str(r['n_correct']) + '/' + str(r['n_fields']):8}"
              f"{r['elapsed']:7.1f}s{r['cost']:10.4f}  {failed}")
    print(f"\n  accuracy {report['accuracy']*100:.0f}%  p50 {report['p50_s']:.1f}s  "
          f"${report['cost_per_contract']:.4f}/contract  wall {report['wall_s']:.0f}s")


# ── Persistence ─────────────────────────────────────────────────────────────
def save_json(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def append_run(entry: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with RUNS_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def load_baseline() -> dict:
    if not BASELINE_FILE.exists():
        sys.exit(f"No baseline yet. Run: python3 {pathlib.Path(__file__).name} baseline")
    return json.loads(BASELINE_FILE.read_text())


def load_runs() -> list:
    if not RUNS_FILE.exists():
        return []
    return [json.loads(line) for line in RUNS_FILE.read_text().splitlines() if line.strip()]


# ── CLI ─────────────────────────────────────────────────────────────────────
def add_lever_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--single-pass", action="store_true",
                   help="one schema-constrained call instead of v0's briefing + essay (levers 3 and round-trip)")
    p.add_argument("--cache", action="store_true", help="cache the playbook prefix (lever 1)")
    p.add_argument("--triage", action="store_true",
                   help="Haiku triage routes ROUTINE to --routine-model, COMPLEX to --complex-model (lever 2)")
    p.add_argument("--routine-model", choices=list(ALIASES), default="opus",
                   help="model for every contract, or for ROUTINE ones with --triage (default: opus)")
    p.add_argument("--complex-model", choices=list(ALIASES), default="opus",
                   help="model for COMPLEX contracts with --triage (default: opus)")
    p.add_argument("--derive-tier", action="store_true",
                   help="compute risk_tier in code from change_of_control and liability_cap_usd (needs --single-pass)")
    p.add_argument("--effort", choices=["low", "medium", "high"], default=None,
                   help="effort dial, Sonnet/Opus only (ignored for Haiku)")
    p.add_argument("--max-tokens", type=int, default=8000, help="output ceiling per call (default 8000)")
    p.add_argument("--workers", type=int, default=0, help="parallel contracts; 0 = sequential (lever 5)")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="ClauseScan terminal runner. See the module docstring for the workflow.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("baseline", help="run ClauseScan v0 once and save results/baseline.json (about $1-2)")
    run = sub.add_parser("run", help="run one configuration on the sample (or holdout) and score it")
    add_lever_flags(run)
    scope = run.add_mutually_exclusive_group()
    scope.add_argument("--holdout", action="store_true",
                       help="run on the two unseen contracts; freeze the config first")
    scope.add_argument("--stress", action="store_true",
                       help="run on the ten harder contracts in stress_set.py")
    run.add_argument("--repeats", type=int, default=1, help="repeat the run N times for variance")
    run.add_argument("--label", default="", help="short name stored with the result")
    probe = sub.add_parser("latency-probe",
                           help="p50 on contracts repeated N times (latency only, not graded)")
    add_lever_flags(probe)
    probe.add_argument("--length-factor", type=int, default=8, help="repeat each contract text N times")
    slide = sub.add_parser("slide", help="print the steering-committee table for a saved run")
    slide.add_argument("--run", type=int, default=-1,
                       help="index into runs.jsonl of a sample run (default: the latest)")
    return ap.parse_args(argv)


def config_from_args(a) -> dict:
    return {"single_pass": a.single_pass, "cache": a.cache, "triage": a.triage,
            "routine_model": ALIASES[a.routine_model], "complex_model": ALIASES[a.complex_model],
            "effort": a.effort, "max_tokens": a.max_tokens, "workers": a.workers,
            "derive_tier": a.derive_tier}


def lever_names(cfg: dict) -> str:
    names = [n for n, on in [("schema-1pass", cfg["single_pass"]), ("cache", cfg["cache"]),
                             ("routing", cfg["triage"]), ("derived-tier", cfg["derive_tier"])] if on]
    if cfg["effort"]:
        names.append(f"effort-{cfg['effort']}")
    if cfg["workers"]:
        names.append(f"parallel-x{cfg['workers']}")
    models = cfg["routine_model"] + ("/" + cfg["complex_model"] if cfg["triage"] else "")
    return "+".join(names) + f" [{models}]" if names else f"none [{models}]"


def cmd_baseline() -> None:
    print("Running ClauseScan v0 on the six-contract sample (sequential; expect 2-4 minutes)...")
    report = run_portfolio(clausescan_v0, CONTRACTS, GOLD)
    print_report(report, "ClauseScan v0 baseline")
    save_json(BASELINE_FILE, {"saved": time.strftime("%Y-%m-%d %H:%M:%S"), **report})
    print(f"\nSaved {BASELINE_FILE}")


def cmd_run(a) -> None:
    cfg = config_from_args(a)
    scope = "HOLDOUT" if a.holdout else "stress" if a.stress else "sample"
    contracts, gold = {"HOLDOUT": (HOLDOUT_CONTRACTS, HOLDOUT_GOLD),
                       "stress": (STRESS_CONTRACTS, STRESS_GOLD),
                       "sample": (CONTRACTS, GOLD)}[scope]
    baseline = load_baseline() if scope == "sample" else None
    print(f"Config: {lever_names(cfg)}   scope: {scope}   repeats: {a.repeats}")
    reports = []
    for i in range(a.repeats):
        report = run_portfolio(lambda c: clausescan_v1(c, cfg), contracts, gold, workers=cfg["workers"])
        print_report(report, f"{a.label or 'run'} #{i + 1} ({scope})")
        score = engagement_score(report, baseline) if baseline else None
        if score is not None:
            gate = "" if report["accuracy"] >= 0.90 else "  accuracy gate FAILED, score zeroed"
            print(f"  SCORE {score} (v0 = 100){gate}")
        append_run({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "label": a.label, "scope": scope,
                    "config": cfg, "levers": lever_names(cfg), "score": score, "report": report})
        reports.append(report)
    if a.repeats > 1:
        accs = [r["accuracy"] for r in reports]
        p50s = [r["p50_s"] for r in reports]
        costs = [r["cost_per_contract"] for r in reports]
        print(f"\nVariance over {a.repeats} runs: accuracy min {min(accs)*100:.0f}% / median "
              f"{statistics.median(accs)*100:.0f}%   p50 {min(p50s):.1f}-{max(p50s):.1f}s   "
              f"cost ${min(costs):.4f}-${max(costs):.4f}/contract")


def lengthen(contract: dict, factor: int) -> dict:
    return {**contract, "text": "\n\n".join([contract["text"]] * factor)}


def cmd_latency_probe(a) -> None:
    cfg = config_from_args(a)
    contracts = [lengthen(c, a.length_factor) for c in CONTRACTS]
    print(f"Latency probe: contracts repeated {a.length_factor}x (graded results are meaningless; "
          f"timing only). Config: {lever_names(cfg)}")
    report = run_portfolio(lambda c: clausescan_v1(c, cfg), contracts, GOLD, workers=cfg["workers"])
    print_report(report, f"latency probe x{a.length_factor}")
    append_run({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "label": f"latency-probe-x{a.length_factor}",
                "scope": "latency-probe", "config": cfg, "levers": lever_names(cfg), "score": None,
                "report": report})


def models_used(*row_sets: list) -> set:
    return {m for rows in row_sets for r in rows for m in r["tokens"]}


def contract_token_counts(rows: list, models: set) -> dict:
    """{contract id: {model: tokens in that contract's text}} via the free count_tokens endpoint."""
    by_id = {c["id"]: c for c in CONTRACTS}
    return {r["id"]: {m: get_client().messages.count_tokens(
                model=m, messages=[{"role": "user", "content": by_id[r["id"]]["text"]}]).input_tokens
            for m in models} for r in rows}


ASSUMPTIONS = {
    "contracts_in_estate": 248_000,
    "production_scale_factor": 8,   # production contracts ~8x the lab sample's contract text
    "interactive_share": 0.15,
    "batch_share": 0.85,
    "fee_per_contract": 0.75,
}


def estate_cogs(rows: list, counts: dict, two_speed: bool, a=ASSUMPTIONS) -> float:
    """Average production cost per contract x estate size. Only contract text scales with length."""
    scale = a["production_scale_factor"]
    per = []
    for r in rows:
        full = production_cost(r["tokens"], counts[r["id"]], scale)
        if two_speed:
            batch = production_cost(r["tokens"], counts[r["id"]], scale, batch=True)
            full = full * a["interactive_share"] + batch * a["batch_share"]
        per.append(full)
    return statistics.mean(per) * a["contracts_in_estate"]


def cmd_slide(a) -> None:
    baseline = load_baseline()
    runs = [r for r in load_runs() if r["scope"] == "sample"]
    if not runs:
        sys.exit("No sample runs saved yet. Run: python3 run_clausescan.py run <levers>")
    run = runs[a.run]
    opt = run["report"]
    counts = contract_token_counts(baseline["rows"], models_used(baseline["rows"], opt["rows"]))
    n, fee = ASSUMPTIONS["contracts_in_estate"], ASSUMPTIONS["fee_per_contract"]
    before = estate_cogs(baseline["rows"], counts, two_speed=False)
    after = estate_cogs(opt["rows"], counts, two_speed=True)
    revenue = n * fee
    rows = [
        ("Accuracy (audited fields, 6-contract sample)", f"{baseline['accuracy']*100:.0f}%", f"{opt['accuracy']*100:.0f}%"),
        ("p50 latency / contract (lab-length)", f"{baseline['p50_s']:.1f}s", f"{opt['p50_s']:.1f}s"),
        ("Lab cost / contract", f"${baseline['cost_per_contract']:.4f}", f"${opt['cost_per_contract']:.4f}"),
        ("Estate COGS, 248K docs (modeled)", f"${before:,.0f}", f"${after:,.0f}"),
        ("Engagement margin on $0.75 fee", f"{(revenue-before)/revenue*100:.0f}%", f"{(revenue-after)/revenue*100:.0f}%"),
        ("Unit COGS, interactive lane, full price (SLA $0.02)", f"${before/n:.4f}",
         f"${estate_cogs(opt['rows'], counts, two_speed=False)/n:.4f}"),
        ("Unit COGS, blended 15% interactive / 85% batch", "n/a", f"${after/n:.4f}"),
    ]
    w = max(len(r[0]) for r in rows)
    print(f"PROJECT HELVETICA -- before / after   (run: {run['levers']}, {run['time']})")
    print(f"{'Metric'.ljust(w)}  {'v0':>12}  {'Optimized':>12}")
    for m, b, o in rows:
        print(f"{m.ljust(w)}  {b:>12}  {o:>12}")
    print("\nAssumptions: " + ", ".join(f"{k}={v}" for k, v in ASSUMPTIONS.items()))
    print("Production cost scales only the contract-text tokens by the scale factor; the playbook "
          "and the JSON output stay fixed. Batch lane = 50% off, cache hits assumed as in the sample. "
          "Prices verified against the pricing page on 2026-10-23.")
    print("Limits: accuracy is 6 contracts / 30 field checks. Latency is measured at lab contract "
          "length; see `latency-probe` for longer text. Production traffic mix is assumed, not measured.")


def main(argv=None) -> None:
    a = parse_args(argv)
    {"baseline": lambda: cmd_baseline(), "run": lambda: cmd_run(a),
     "latency-probe": lambda: cmd_latency_probe(a), "slide": lambda: cmd_slide(a)}[a.cmd]()


if __name__ == "__main__":
    main()
