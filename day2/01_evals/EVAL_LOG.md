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
