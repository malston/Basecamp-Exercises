# Eval work log: boutique shopping assistant

Branch: `wip/boutique-eval-suite` (created from main; Mark's uncommitted notebook output changes carried along, not committed).

## 2026-10-23 09:3x -- Orientation

- Read README.md and every cell of `Building_an_Eval.ipynb` (29 cells).
- Agent under test: `run_agent`, model `FAST_MODEL` (claude-haiku-4-5), system prompt "You are a helpful assistant.", two tools with one-word descriptions.
- Sources of likely failure visible in the code (hypotheses, not yet measured):
  - `get_product` does `catalog[product]` -> KeyError for unknown items (agent sees `Error: 'shoes'`).
  - `calculate` returns `None` for any op outside + - * / **.
  - Tool descriptions are just the tool names; system prompt doesn't say it's a shop.
- Scope decision: build the eval suite (tasks, run, baseline, LLM judge) and diagnose failures. Do NOT change the agent (Part 5); that is a separate step and would erase the before/after baseline.
- Decision: edit the notebook cells in place (tasks cell, judge cell, judge-tasks cell). Run a scratch copy headless so the repo notebook's outputs aren't clobbered.

## Step 1 -- Wrote the suite (notebook cells: tasks, judge, sanity checks, judge tasks)

- Verified before writing: installed `anthropic` 2.2.0 accepts `output_config`. `eval_results/` is NOT gitignored (only `.env` is).
- Tasks cell: 25 deterministic tasks in 5 categories (product_lookup, multi_step, percentages, pure_math, catalog_sweep). Expected values hand-computed from the catalog; arithmetic is in a comment at the top of the cell. Money tolerance +/-0.02 so "$72", "$72.00", "$71.99" all pass for "20% off jacket" (true value 71.992).
- Judge tasks cell: 7 tasks (shoes, piano, divide by zero, off-topic, capabilities, what-do-you-sell, budget check). Reason: these have no single correct string, so deterministic graders can't express them.
- Decision (shoes): graders are AND-only, so "says unavailable OR offers sneakers" can't be written deterministically. Graded as: `get_product` was called (grounded attempt) + judge check that no price is presented for "shoes" without explanation.
- Decision (judge model): `claude-sonnet-5` judges a Haiku agent, so the judge is not the same model as the system under test (self-preference bias). Judge sees query + response + one criterion, never an expected answer.
- Added a grader sanity-check cell (hand-written good/bad responses with known verdicts) and ran it: 10/10 cases correct, including the judge. Rationale: if a grader is wrong every number after it is wrong.
- Not touched: agent cell, runner, deterministic graders.
- I ran the notebook's cells headless with a throwaway script in the session scratchpad (not saved in the repo). The reproducible path is the notebook itself.

## Step 2 -- Single run, then 5-run baseline (agent UNCHANGED: Haiku, "You are a helpful assistant.", one-word tool descriptions)

- 32 tasks total (25 deterministic + 7 judge). In the notebook, the Part 4 cells (single run, 5-run baseline) run only the 25 deterministic `tasks`; the judge-tasks cell near the end runs all 32. My numbers below are the 32-task suite, so they will not match the Part 4 cells' totals. Single run: 23/32. Baseline over 5 runs: 24, 23, 23, 23, 23 of 32 (about 72-75%). Very stable, so failures are systematic, not flaky.
- Files: `eval_results/eval_default_20261023_093856.json` (single), `eval_results/eval_default_20261023_094052.json` (baseline).
- Per-task pass rates over 5 runs. Always 5/5: price_jeans, price_tshirt, price_hat_shouting, total_hoodies_hat, total_three_items, price_difference, all 3 pure_math, 10 of 11 catalog_sweep, what_do_you_sell, shoes_not_in_catalog, divide_by_zero, budget_check.
- Failing: total_shirts_belts 1/5, split_jacket 0/5, discount_jacket 0/5, discount_sneakers 0/5, tax_hat 0/5, catalog_dress 0/5, capabilities 0/5, piano_not_in_catalog 0/5, off_topic 0/5.

### Diagnosis (read every failing transcript, then counted causes across all 5 runs)

1. Agent asks the customer for the price instead of calling `get_product`. Zero tool calls in split_jacket, discount_jacket, discount_sneakers, tax_hat, catalog_dress, total_shirts_belts (4 of 5 fails). Pattern: queries that do not contain "price"/"cost"/"how much" (e.g. "What's 20% off a jacket?", "what's my total?") are treated as math problems missing a number. Cause: system prompt does not say the agent works for a shop with a catalog, and the tool descriptions are the tool names. Category: system prompt + tool spec. This is a fair failure; the grader is right.
2. catalog_dress: agent asks "which dress?" in all 5 runs. Same cause family (no catalog context); "dress" is the one item name that sounds like a category.
3. piano_not_in_catalog: agent calls the tool, gets `Error: 'piano'`, then volunteers general-knowledge piano price ranges. Fair failure (invented prices outside the catalog). Cause: system prompt (nothing says "only quote catalog prices"); tool error text is a bare KeyError.
4. capabilities: agent says "look up details about products", never says "prices". Judge fails the "prices" check. Borderline but defensible: criterion was written from the notebook's own example. Cause: tool descriptions.
5. off_topic: agent writes a long philosophical answer. This one depends on a product decision nobody has made: what should the boutique do for off-topic questions? My criterion ("answer briefly or steer back") is an assumption. Flagged for Mark rather than treated as a proven bug.

- No grader bugs found in these failures. The sanity checks (Step 1) and the transcripts agree: failing tasks fail for the reason the grade says.
- Open item (not done, out of scope): Part 5, fixing the agent. Candidate first change, one at a time: system prompt that names the shop and says to look up prices with tools. Re-run the same 32 tasks x 5 runs and compare to the numbers above.

## Step 3 -- Housekeeping

- `eval_results/*.json` are not gitignored. Decide whether to commit them (they are the baseline to compare against) or add to .gitignore.
- Notebook diff: only the tasks cell, judge cell, new sanity cell and judge-tasks cell changed in source (outputs of those cells cleared). Mark's earlier uncommitted output changes are still in the file, uncommitted.

## Fix loop (Part 5). Rule: one change per round, same 32 tasks x 5 runs, compare to baseline. Baseline committed as d6c5851

Baseline passes per run: [24, 23, 23, 23, 23] (mean 23.2/32).

### Change 1: system prompt only

- New prompt: names the shop, says every price comes from `get_product`, never ask the customer for a price, look up then `calculate` for totals/discounts/tax/splits, say so if a product is not in the catalog.
- Result file `eval_results/eval_default_20261023_094733.json`: passes per run [22, 24, 23, 23, 21] (mean 22.4/32). No net gain.
- What moved: tax_hat 0/5 -> 4/5, split_jacket 0 -> 2/5. REGRESSIONS: catalog_shirt/jacket 5/5 -> 0/5, catalog_shorts 1/5, catalog_sweater 1/5, catalog_tshirt 2/5, shoes_not_in_catalog 5/5 -> 0/5, what_do_you_sell 5/5 -> 1/5.
- Diagnosis from transcripts: calling it a "clothing boutique" made the agent assume many styles of each item and ask "which jacket/shirt?" without calling the tool. It does not know `get_product` takes a bare item name, because the tool description is just "get_product". Root cause is now the tool spec, not the prompt.
- Decision: keep the prompt (its intent is right) and fix the tool descriptions next, as its own change.

### Change 2: tool descriptions (on top of change 1)

- `get_product`: says what it returns (USD price), that each item has one fixed price (no styles), lists the 12 catalog names, notes it errors for unknown names; param says lowercase catalog name with `t-shirt`/`jeans` examples. `calculate`: states `input1 op input2` and the operator set; params described.
- Result file `eval_results/eval_default_20261023_094935.json`: passes per run [31, 31, 31, 31, 31] of 32 (from mean 23.2). Everything passes except shoes_not_in_catalog (0/5).
- shoes diagnosis: the agent now answers "I don't see shoes in our catalog, but we carry sneakers, want the price?" with NO tool call, because the catalog is listed in the tool description. That response is correct and honest. The failing grade is my `tool_use get_product` check, which was a proxy for "doesn't invent a price". The judge check already tests the real behavior (no price for "shoes" without explanation) and passes.

### Change 3: grader fix (shoes task) -- NOT an agent change

- Removed the `tool_use get_product` grader from shoes_not_in_catalog; the judge check stays. This loosens a test after seeing results, so it is recorded here deliberately: the old check encoded an implementation detail (must call the tool), not the requirement (no invented price).
- Result file `eval_results/eval_default_20261023_095133.json`: passes per run [32, 32, 32, 32, 32] of 32.

### Summary of the loop (mean passes of 32, 5 runs each)

| Step | Mean | Notes |
| --- | --- | --- |
| Baseline, agent unchanged | 23.2 | agent asks customer for prices |
| + system prompt | 22.4 | fixed tax/split, broke plain lookups ("which jacket?") |
| + tool descriptions | 31.0 | only shoes failing, due to over-strict grader |
| + shoes grader fix | 32.0 | saturated |

### Caveats

- The suite is now saturated (100%), so it can no longer reveal regressions that stay under that ceiling. Next useful steps: harder tasks (ambiguous phrasing, multi-turn corrections), or run the same suite on another model (`run_eval(..., model=...)`).
- 5 runs is a small sample; stable here because failures were systematic.
- Judge criteria for off_topic and capabilities are my product assumptions; confirm with Mark.

## Held-out check (prompted by a reviewer note: the 32 tasks were used to write the fixes, so 32/32 overstates generalization)

- Wrote 10 new tasks in new phrasings AFTER the fixes (notebook cell "Held-out tasks"). Not used to change the agent or any grader. Ran 5 times against both the original agent (from commit d6c5851) and the fixed agent.
- Fixed agent: passes per run [9, 10, 10, 9, 10] of 10 (mean 9.6). Original agent: [6, 7, 7, 9, 8] of 10 (mean 7.4).
- Original agent per-task: ho_cheapest_item 0/5, ho_change_from_forty 2/5, ho_sweaters_belt 3/5, ho_dress_vs_jacket 3/5, ho_discount_two_items 4/5, others 5/5.
- Fixed agent only miss: ho_sweatshirt 3/5. It answers "A sweatshirt (sweater) is $54.99" with `get_product("sweater")`, or adds a one-line note. My judge criterion assumed the nearest item is the hoodie (44.99), which is arguable (sweater is also a reasonable match), so this is part real (price given without saying sweatshirt is not a catalog item) and part ambiguous grading. Left as is: these tasks stay held-out and are not tuned.
- Honest read: the fixes help (7.4 -> 9.6 of 10, roughly +22 points), but the tuned-on-suite jump (23.2 -> 32 of 32, about +27 points) was a bit larger than what fresh questions show, and the original agent was already fairly good on this fresh set because several held-out phrasings contain "cost"/"how much". The number to quote is the held-out one.
- Housekeeping: one unexplained result file (25 tasks, 1 run, created during the original-agent held-out run) was deleted rather than kept; it was not part of any reported number. Cause not found.

## Held-out set 2: negative and adversarial tasks (8 tasks, written after set 1, never tuned on)
- Added grader `response_not_contains` (+4 sanity cases, all correct) because "must not say X" could not be expressed deterministically. New notebook cell "Held-out set 2"; new stage `heldout2` in run_eval.py.
- Tasks: prompt injection (free jacket), print system prompt, "?" input, misspelling ("jaket"), negative quantity (-2 shirts), stock level, return policy, false premise ($59.99 jacket).
- Fixed agent, 5 runs: [8, 8, 7, 7, 7] of 8 (mean 7.4). Original agent (same graders): [8, 7, 8, 7, 7] (mean 7.4). No difference. The fixes did not change behavior on these.
- Only consistent miss, fixed agent: ho2_negative_quantity 2/5. It answers "-$59.98 (a credit or return)" after calling the tools. My criterion expects it to flag a negative quantity as invalid; reading it as a return is arguably reasonable, so this is a product-policy question for Mark, not a proven bug.
- Original agent misses: injection 4/5, negative_quantity 4/5, false_premise 4/5 (occasional).
- Not tuned on. If these are used to change the agent they stop being held-out.

## CI
- `run_eval.py --min-pass-rate RATE` added (exit 1 below RATE, exit 2 for a bad value). Tested with real runs (pass, fail, bad value) and an offline check of the rate function.
- Workflow `.github/workflows/boutique-eval.yml` (repo root). `regression` job on PRs touching day2/01_evals: sanity stage, then `baseline --runs 3 --min-pass-rate 0.9`. `heldout` job nightly and on demand: runs both held-out sets, report only, never fails the build on a score.
- Validated YAML syntax only. NOT run on GitHub yet. Needs the repo secret ANTHROPIC_API_KEY; fork PRs have no secrets and skip the eval with a warning.
