"""Offline tests for run_clausescan.py (no API calls). Run: python3 -m pytest test_run_clausescan.py -q"""
import pytest

import run_clausescan as rc


def tokens(inp=0, cw=0, cr=0, out=0):
    return {"in": inp, "cw": cw, "cr": cr, "out": out}


# ── cost ────────────────────────────────────────────────────────────────────
def test_cost_uses_verified_sonnet_5_prices():
    # $2 in / $10 out per MTok: 1M in + 1M out = $12
    assert rc.cost_of(rc.MODEL_SONNET, tokens(inp=1_000_000, out=1_000_000)) == pytest.approx(12.0)


def test_cost_cache_write_is_1_25x_and_read_is_0_1x():
    # Opus 4.8: $5 input. 1M write = $6.25, 1M read = $0.50
    assert rc.cost_of(rc.MODEL_OPUS, tokens(cw=1_000_000)) == pytest.approx(6.25)
    assert rc.cost_of(rc.MODEL_OPUS, tokens(cr=1_000_000)) == pytest.approx(0.50)


def test_batch_halves_every_term():
    t = tokens(inp=1000, cw=1000, cr=1000, out=1000)
    assert rc.cost_of(rc.MODEL_HAIKU, t, batch=True) == pytest.approx(rc.cost_of(rc.MODEL_HAIKU, t) / 2)


def test_unknown_model_raises():
    with pytest.raises(KeyError):
        rc.cost_of("claude-nope", tokens(inp=1))


# ── grading (copied from the exercise; guard against bad copy) ──────────────
def test_grade_perfect_contract_scores_5_of_5():
    gold = rc.GOLD["C-105"]
    fields = {"auto_renewal": True, "change_of_control": True, "liability_cap_usd": None,
              "governing_law": "Texas", "risk_tier": "HIGH"}
    assert sum(rc.grade_fields(fields, gold).values()) == 5


def test_grade_stale_cap_on_amended_contract_fails_only_cap_and_tier():
    gold = rc.GOLD["C-105"]
    fields = {"auto_renewal": True, "change_of_control": True, "liability_cap_usd": 1000000,
              "governing_law": "Texas", "risk_tier": "MEDIUM"}
    checks = rc.grade_fields(fields, gold)
    assert not checks["liability_cap_usd"] and not checks["risk_tier"]
    assert sum(checks.values()) == 3


def test_grade_missing_fields_fails_everything_but_null_cap_and_false_flags():
    checks = rc.grade_fields(None, rc.GOLD["C-104"])
    assert checks["liability_cap_usd"] is True  # gold cap is null and None matches
    assert checks["governing_law"] is False


# ── score ───────────────────────────────────────────────────────────────────
BASE = {"cost_per_contract": 0.10, "p50_s": 40.0}


def test_score_of_baseline_is_100():
    assert rc.engagement_score({"accuracy": 1.0, **BASE}, BASE) == 100


def test_score_is_zero_below_accuracy_gate():
    assert rc.engagement_score({"accuracy": 0.8, "cost_per_contract": 0.01, "p50_s": 1.0}, BASE) == 0


def test_score_4x_cheaper_2x_faster_is_300():
    r = {"accuracy": 0.9, "cost_per_contract": 0.025, "p50_s": 20.0}
    assert rc.engagement_score(r, BASE) == 300


# ── production-scale cost model ─────────────────────────────────────────────
def test_production_cost_scales_only_contract_tokens_not_playbook_or_output():
    # one Sonnet call: 100 uncached tokens of contract, 5000 cache-read playbook, 200 out
    row_tokens = {rc.MODEL_SONNET: {"calls": 1, **tokens(inp=100, cr=5000, out=200)}}
    contract_tokens = {rc.MODEL_SONNET: 100}
    base = rc.cost_of(rc.MODEL_SONNET, row_tokens[rc.MODEL_SONNET])
    scaled = rc.production_cost(row_tokens, contract_tokens, scale=8)
    extra = 7 * 100 * 2.00 / 1e6  # only the contract text grows
    assert scaled == pytest.approx(base + extra)


def test_production_cost_scale_one_equals_lab_cost():
    row_tokens = {rc.MODEL_HAIKU: {"calls": 2, **tokens(inp=500, out=50)}}
    assert rc.production_cost(row_tokens, {rc.MODEL_HAIKU: 200}, scale=1) == pytest.approx(
        rc.cost_of(rc.MODEL_HAIKU, row_tokens[rc.MODEL_HAIKU]))


# ── summaries ───────────────────────────────────────────────────────────────
def test_summarize_rows_accuracy_p50_cost():
    rows = [
        {"n_correct": 5, "n_fields": 5, "elapsed": 1.0, "cost": 0.01},
        {"n_correct": 4, "n_fields": 5, "elapsed": 3.0, "cost": 0.03},
        {"n_correct": 5, "n_fields": 5, "elapsed": 2.0, "cost": 0.02},
    ]
    s = rc.summarize_rows(rows)
    assert s["accuracy"] == pytest.approx(14 / 15)
    assert s["p50_s"] == 2.0
    assert s["cost_per_contract"] == pytest.approx(0.02)


# ── CLI ─────────────────────────────────────────────────────────────────────
def test_run_defaults_to_the_v0_config():
    a = rc.parse_args(["run"])
    assert not a.single_pass and not a.cache and not a.triage and a.workers == 0
    assert a.routine_model == "opus" and a.complex_model == "opus"


def test_run_flags_parse():
    a = rc.parse_args(["run", "--single-pass", "--cache", "--triage", "--routine-model", "haiku",
                       "--complex-model", "sonnet", "--effort", "low", "--max-tokens", "1000",
                       "--workers", "4", "--repeats", "3", "--holdout", "--label", "x"])
    assert a.single_pass and a.cache and a.triage and a.holdout
    assert (a.routine_model, a.complex_model, a.effort) == ("haiku", "sonnet", "low")
    assert (a.max_tokens, a.workers, a.repeats, a.label) == (1000, 4, 3, "x")


def test_bad_model_alias_is_rejected():
    with pytest.raises(SystemExit):
        rc.parse_args(["run", "--routine-model", "gpt"])


def test_config_effort_dropped_for_haiku():
    a = rc.parse_args(["run", "--single-pass", "--routine-model", "haiku", "--effort", "low"])
    cfg = rc.config_from_args(a)
    assert cfg["routine_model"] == rc.MODEL_HAIKU
    assert rc.effort_for(cfg, rc.MODEL_HAIKU) is None
    assert rc.effort_for(cfg, rc.MODEL_SONNET) == "low"


def test_stress_set_is_complete_and_disjoint_from_sample():
    ids = [c["id"] for c in rc.STRESS_CONTRACTS]
    assert len(ids) == len(set(ids)) == 10
    assert set(ids) == set(rc.STRESS_GOLD)
    assert not set(ids) & {c["id"] for c in rc.CONTRACTS + rc.HOLDOUT_CONTRACTS}
    for gold in rc.STRESS_GOLD.values():
        assert set(gold) == {"auto_renewal", "change_of_control", "liability_cap_usd",
                             "governing_law", "risk_tier"}


def test_stress_gold_risk_tier_follows_the_playbook_rule():
    for cid, g in rc.STRESS_GOLD.items():
        flags = int(g["change_of_control"]) + int(g["liability_cap_usd"] is None)
        assert g["risk_tier"] == {0: "LOW", 1: "MEDIUM", 2: "HIGH"}[flags], cid


def test_stress_flag_parses_and_excludes_holdout():
    assert rc.parse_args(["run", "--stress"]).stress
    with pytest.raises(SystemExit):
        rc.parse_args(["run", "--stress", "--holdout"])


@pytest.mark.parametrize("coc,cap,tier", [
    (True, None, "HIGH"), (True, 500000, "MEDIUM"), (False, None, "MEDIUM"), (False, 1000, "LOW")])
def test_derive_risk_tier_applies_the_playbook_rule(coc, cap, tier):
    out = rc.derive_risk_tier({"change_of_control": coc, "liability_cap_usd": cap, "risk_tier": "LOW"})
    assert out["risk_tier"] == tier


def test_derive_risk_tier_does_not_mutate_input_and_tolerates_missing_fields():
    fields = {"change_of_control": True, "liability_cap_usd": None, "risk_tier": "LOW"}
    rc.derive_risk_tier(fields)
    assert fields["risk_tier"] == "LOW"
    assert rc.derive_risk_tier(None) is None
    assert rc.derive_risk_tier({"risk_tier": "LOW"}) == {"risk_tier": "LOW"}


def test_derive_tier_flag_in_config():
    assert rc.config_from_args(rc.parse_args(["run", "--derive-tier"]))["derive_tier"] is True
    assert rc.config_from_args(rc.parse_args(["run"]))["derive_tier"] is False


def test_models_used_unions_models_across_row_sets():
    before = [{"tokens": {rc.MODEL_OPUS: {}}}]
    after = [{"tokens": {rc.MODEL_SONNET: {}, rc.MODEL_HAIKU: {}}}]
    assert rc.models_used(before, after) == {rc.MODEL_OPUS, rc.MODEL_SONNET, rc.MODEL_HAIKU}


def test_import_has_no_side_effects_and_needs_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert rc.PLAYBOOK  # data loaded at import; no client built
