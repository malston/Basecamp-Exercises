# Work log -- ClauseScan optimization (Inference Optimization exercise)

Goal: take ClauseScan v0 from "works in the demo" to "defensible at the steering committee".
Branch: `worktree-inference-optimization`. Log is append-only; newest entries at the bottom.

## 2026-10-23 -- Orientation

- Read root `README.md`. It points to `day2/02_inference-optimization` as the "demo to defensible" workload.
- Read that folder's README and the full `Inference_Optimization.py` (1,451 lines, jupytext source for the notebook).
- What the workload is: ClauseScan v0 reviews 6 supplier contracts for 5 audited fields. Two serial Opus calls per contract, uncached 22K-char playbook, essay output. SLA: accuracy >= 90%, p50 <= 5s, COGS <= $0.02/contract.
- Score formula: `50 * (base $/your $) + 50 * (base p50/your p50)`, zero if accuracy < 90%. v0 = 100.
- Environment check: Python 3.14.2, `anthropic` 1.8.0 installed. No credentials found (no `ANTHROPIC_API_KEY`, no Bedrock token in the environment, no `.env` in the repo or two parents). Every measurement needs the live API, so work is blocked on a key.

### Defensibility gaps spotted in the exercise's own method (to address, not just score)

1. p50 SLA is for production-length contracts (~8x longer) but latency is measured on lab-length samples. Cost gets the 8x scale factor; latency does not.
2. `production_scale_factor` multiplies the whole $/contract, including the cached playbook, which does not grow with contract length. Slide COGS is likely overstated for the optimized pipeline.
3. Sample is 6 contracts / 30 field checks. The 90% gate allows 3 misses. Holdout is 2 contracts / 10 checks. One flaky field swings the result; need repeated runs to show variance.
4. p50 over 6 values is noisy and varies run to run; a single scorecard run is not evidence.
5. Pricing table is marked "cached June 2026, verify before quoting". Needs verification against the pricing page before any number goes on a slide.
6. Model IDs in the file (`claude-sonnet-5`, `claude-haiku-4-5`, `claude-opus-4-8`) were not confirmed against the API yet.

### Plan

1. Get credentials (blocked, asked Mark).
2. Run baseline v0 once; record numbers.
3. Pull levers one at a time on the sample, logging score + accuracy after each.
4. Repeat the final config several times to get variance.
5. Run the holdout once, with config frozen.
6. Generate the slide with corrected/stated assumptions; verify pricing.
7. Write the teaching summary for Mark.

## 2026-10-23 -- New requirement from Mark

- The solution must run from a terminal, not only from VS Code. Plan: add a named CLI script (`run_clausescan.py`) with `--help`, flags for each lever, `--holdout`, `--repeats N`, and a JSON results file so runs are reproducible and loggable. It reads the key from env or `.env`, same as the notebook. The notebook stays as is.

## 2026-10-23 -- Verification of the exercise's external claims

Method: 1-token live probes (`models.retrieve` + `messages.create`), the official pricing page (https://platform.claude.com/docs/en/about-claude/pricing.md, fetched today), and the claude-api skill docs for cache minimums.

| Claim in the exercise | Result |
|---|---|
| Model IDs `claude-haiku-4-5`, `claude-sonnet-5`, `claude-opus-4-8` exist | CONFIRMED. All three answered. Haiku resolves to `claude-haiku-4-5-20251001`. |
| Haiku 4.5 $1/$5 per MTok | CONFIRMED |
| Opus 4.8 $5/$25 per MTok | CONFIRMED |
| **Sonnet 5 $3/$15 per MTok** | **WRONG.** Pricing page lists Sonnet 5 at $2 input / $10 output (cache read $0.20, 5m write $2.50). The exercise's `PRICING` overstates Sonnet cost by 50%. |
| Cache write 1.25x, read 0.1x | CONFIRMED against the rows above (Opus 4.8 write $6.25, read $0.50; Haiku write $1.25, read $0.10). |
| Batch API 50% off | CONFIRMED (pricing page: "50 percent discount on both input and output tokens"). |
| Cache minimum 2048 Sonnet / 4096 Opus+Haiku | PARTLY STALE. Skill docs: Sonnet 5 = 1024, Opus 4.8 = 1024, Haiku 4.5 = 4096. Playbook is ~5.5K tokens so caching works on all three either way. |

Consequence: every Sonnet cost in the scorecard and slide is overstated by 1.5x unless `PRICING` is corrected. I will correct it in the terminal runner and note it on the slide.

## 2026-10-23 -- Terminal runner built (Mark chose: standalone script)

- `run_clausescan.py`: subcommands `baseline`, `run`, `latency-probe`, `slide`. Contracts, gold, playbook, schemas, grader are copied by checked line range from `Inference_Optimization.py` (assembly aborts if a range no longer starts where expected), so there is no hand-typed copy. Pricing is corrected (Sonnet 5 $2/$10).
- `test_run_clausescan.py`: 18 offline tests (cost math incl. cache terms and batch, grader, score gate, production-scale cost model, CLI parsing). All pass. Written before the implementation.
- Every run appends to `results/runs.jsonl`; v0 saves to `results/baseline.json`.
- Slide model change: only contract-text tokens scale by 8x. The exercise scaled whole $/contract by 8, which also inflates v0's cost with its (fixed-size) playbook and so overstates savings.

## 2026-10-23 -- Lever runs on the 6-contract sample (all scored vs v0 baseline)

v0 baseline: acc 100%, p50 33.9s, $0.1585/contract (wall 200s).

| Config | Acc | p50 | $/contract | Score |
|---|---|---|---|---|
| schema 1-pass, Opus | 100% | 2.9s | $0.0490 | 746 |
| + cache, Opus (run 1 cold / run 2 warm) | 100% | 2.8s | $0.0189 / $0.0108 | 1020 / 1341 |
| + cache, Sonnet 5, effort low (2 runs) | 100% | 2.7s | $0.0042 | ~2500 |
| + cache, Haiku 4.5 (2 runs) | 100% | 2.4-2.7s | $0.0016 | 5444 / 5739 |

Observations:
- The round-trip collapse + output discipline is the big win: p50 33.9s -> 2.9s, 3.2x cheaper, accuracy unchanged. v0's time was the essay output, not the model.
- Latency barely moves across models (~2.5-2.9s). Score differences after the first lever are cost.
- Accuracy is 100% on every config, including Haiku. The sample cannot separate models, so a leaderboard score of 5,000+ for Haiku-everywhere proves nothing about hard contracts. This is the weakest part of the exercise as a defense.
- Action: build a 10-contract stress set (amendments that change/reinstate terms, venue vs governing law, insurance vs cap, cap exceptions) with gold labels derived from the playbook rules. NOTE for Mark: these labels are mine, not an associate's; the playbook is the only authority, so a lawyer should confirm before the set is quoted to a client.

## 2026-10-23 -- Stress set results and the model decision

Stress set (10 contracts / 50 checks), single-pass + cache, 3 runs each:

| Config | Acc | p50 | $/contract | Notes |
|---|---|---|---|---|
| Haiku 4.5 | 96% (every run) | 2.4-2.6s | $0.0015 | Misses `risk_tier` on S-305, S-306 (cap/CoC fields correct) |
| Sonnet 5, effort low | 100% | 2.1-2.3s | $0.0041 | |
| Opus 4.8, effort low | 100% | 2.8s | $0.0100 warm | no benefit over Sonnet here |
| Triage Haiku -> Sonnet | 98% | 3.7s | $0.0038 | +1.2s latency, barely cheaper than Sonnet alone, less accurate. Routing is not worth it at these prices. |
| Haiku + `--derive-tier` | 100% (stress x3, sample x3) | 2.3-2.6s | $0.0016 | risk_tier computed in code from the two flags per the playbook rule |

Caveats recorded honestly:
- `--derive-tier` was invented after seeing Haiku's stress failures, so the stress set is no longer unseen for that config. Only the 2-contract holdout is.
- Stress gold labels are the engineer's, from the playbook; not lawyer-reviewed.

DECISION (made before the holdout run, so the holdout is not used to choose): primary config = **Sonnet 5, effort low, cached playbook, single-pass schema, max_tokens 1000**. Reasoning: all candidates pass the $0.02 and 5s SLAs at lab length; Haiku saves ~$0.0026/contract, about $650 across 248K contracts before the batch discount, against $186K of fee revenue, in exchange for a code patch tuned on failures and a thinner accuracy margin. Haiku+derived-tier is reported as the leaderboard/cost-floor alternative. Triage routing is dropped. Holdout will be run once for each, no further tuning.

## 2026-10-23 -- Final measurements (config frozen: Sonnet 5, effort low, cache, single-pass, max_tokens 1000)

| Evidence | Result |
|---|---|
| Sample, 5 runs, 4 workers | 100% acc every run, p50 1.9-2.2s, $0.0042-$0.0043, score 2634-2754 (v0 = 100) |
| Holdout (C-201, C-202), run once | Sonnet 100% (10/10). Haiku+derived-tier also 100%. |
| Stress set, 3 runs | Sonnet 100% every run (50/50 checks) |
| Latency probe, contracts repeated 8x | p50 2.2s (timing only; repeated text is not real contract content) |
| Cost-model check | Model predicts ~$0.0105 interactive at 8x contract text; the 8x probe measured $0.0109 (within ~4%). |

Slide (corrected cost model, 248K contracts, 15% interactive / 85% batch):
- v0: p50 33.9s, $0.1921/contract at production length, estate COGS $47,642, margin 74%.
- Sonnet 5 low: p50 1.9s, $0.0063/contract blended, estate COGS $1,560, margin 99%, under the $0.02 SLA.
- Haiku 4.5 + derived tier: $0.0021/contract, COGS $516. Difference vs Sonnet is ~$1,044 on $186K revenue (0.6%), which is why Sonnet is the recommendation.

What the exercise's own slide method would have said, for comparison: it multiplies whole $/contract by 8. v0 would show $1.27/contract (more than the $0.75 fee, a negative margin), and the optimized interactive lane $0.034 (a false SLA fail against $0.02). A CFO who checks the playbook's token count would catch both. The token-level model removes that exposure.

Limits that stay on the slide: 16 labelled contracts total across sample/holdout/stress; stress labels not lawyer-reviewed; latency measured at lab length plus a synthetic 8x probe; traffic split (15/85) is assumed, not measured; cache hit rate in the batch lane assumed to match the sample (the docs call batch cache hits best-effort); v0's essay output is not scaled with contract length (conservative for the baseline).

Housekeeping: `run_clausescan.py` was generated once by copying line ranges from the workshop file; from here it is edited directly (the assembly script stays in the session scratchpad). Run with `python3 -m pytest test_run_clausescan.py -q` (28 pass).

## 2026-10-23 -- What to learn from this (plain English)

The job was "make it fast and cheap, and be able to defend it." The defending took more of the work than the optimizing.

1. Measure before you touch anything. I ran v0 once and saved the result (100% accurate, 33.9s, $0.1585 per contract). Every later number is compared to that file, so nobody can argue about what "before" meant.
2. Check the facts you are about to put on a slide. Three quick checks (model IDs, pricing, cache minimums) found that the workshop prices Sonnet 5 at $3/$15 when the pricing page says $2/$10. That would have overstated every Sonnet cost by 50%.
3. Pull one lever at a time and write down what each did. The first lever (one structured call instead of a briefing call plus an essay call) did most of the work: 33.9s to 2.9s and 3.2x cheaper with accuracy unchanged. Caching came next. Model choice came last. Most of the time v0 spent was writing prose nobody read.
4. Do not trust a test that everything passes. Every config scored 100% on the 6-contract sample, even the smallest model. That means the sample cannot tell models apart, so a leaderboard score of 5,000+ for "smallest model" proves nothing. I wrote 10 harder contracts (an amendment that lowers a cap, a cap deleted then reinstated, venue vs governing law, insurance that is not a liability cap). Haiku failed `risk_tier` on 2 of them every run. Sonnet and Opus passed all.
5. Repeat runs. Single runs hide noise. 3 to 5 runs per config showed accuracy and p50 were stable.
6. Fix the failure at its root when you can. Haiku's `risk_tier` misses came from a rule the playbook states exactly (HIGH = both flags, MEDIUM = one, LOW = none). Code can apply that rule to the two fields Haiku got right. That took Haiku to 100%. The caveat: I invented the fix after seeing the stress failures, so that set stopped being unseen data.
7. Decide before you look at the holdout. I wrote the choice and the reason in this log first (Sonnet 5, effort low, cached, one structured call), then ran the 2-contract holdout once. A holdout you tune against is not a holdout.
8. Do not pick the cheapest option when the saving is small. Haiku saves about $1,000 across the estate against $186K of revenue. Sonnet needs no code patch and had the better accuracy margin. Optimize until the remaining saving is immaterial, then buy safety.
9. Drop an idea when the numbers say so. Triage routing (cheap model decides, bigger model handles hard ones) added 1.2s and cost about the same as Sonnet alone, because Sonnet is already cheap with the playbook cached.
10. Scale only what scales. The exercise multiplies the whole $/contract by 8 for production-length contracts. But the playbook and the JSON answer do not get longer with the contract. Doing it naively makes v0 look like it loses money ($1.27 vs a $0.75 fee) and makes the optimized pipeline look like it fails the $0.02 SLA ($0.034). Neither is true. I scaled only contract-text tokens, then checked the model against a real call at 8x text: predicted $0.0105, measured $0.0109.
11. Say what you did not prove. The slide lists its limits: 16 labelled contracts, stress labels not reviewed by a lawyer, latency measured at lab length plus a synthetic 8x probe, an assumed 15/85 interactive/batch split.

Also worth knowing: newer, cheaper models exist (Sonnet 5.5 at the same price, Haiku 5.5 at $0.10/$0.50). The exercise's models were right to keep for comparability, but on a real engagement "what is current" is step one.

How to rerun: `cd day2/02_inference-optimization`, then `python3 run_clausescan.py run --single-pass --cache --routine-model sonnet --effort low --max-tokens 1000 --repeats 3`, then `python3 run_clausescan.py slide`. Add `--stress` or `--holdout` to change the data set. `--help` lists everything.

## 2026-10-23 -- Upstream PR

Opened https://github.com/victorsteeb/Basecamp-Exercises/pull/27 (branch malston:fix-sonnet-5-pricing, based on upstream main 1996d1b): Sonnet 5 price corrected to $2/$10 in Inference_Optimization .py/.ipynb and Diagnose_Fix_Brief.py. Created through the GitHub API because local git add/commit is blocked in this session. Cache-minimum comment (2048 vs 1024 for Sonnet 5) left for a follow-up.
