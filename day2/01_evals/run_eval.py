#!/usr/bin/env python3
"""Run the boutique eval from a shell, without opening Jupyter.

Use when: you want to run the eval from a terminal or script. It executes the
notebook's code cells (skipping the interactive chat cell) and runs one stage.
Results are saved to eval_results/ as JSON; the terminal shows a short summary.

Run from this folder with the project venv, which holds the anthropic package:
    .venv/bin/python run_eval.py sanity
    .venv/bin/python run_eval.py baseline --runs 5

Stages:
  sanity    grader sanity checks only (hand-written answers with known verdicts)
  single    one run of the 32-task suite (25 deterministic + 7 LLM-judge)
  baseline  --runs N of the 32-task suite, per-task pass rates printed
  heldout   --runs N of the 10 held-out tasks (never used to tune the agent)
  heldout2  --runs N of the 8 negative/adversarial held-out tasks (also never tuned on)

CI gate: add --min-pass-rate 0.9 to exit 1 when the mean pass rate drops below 90%.

Credentials: ANTHROPIC_API_KEY in the environment or in a .env file, same as the notebook.
"""
import argparse
import json
import sys
from collections import defaultdict

SETUP_CELLS = (
    "# Install dependencies",
    "import os\n\ndef _status",
    "import math",
    "# ── Graders",
    "# ── Eval Runner",
    "# ✏️ YOUR TURN",
    "# Implement the LLM-as-judge grader",
)


HELDOUT_SETS = {
    "heldout": ("# Held-out tasks", "heldout_tasks"),
    "heldout2": ("# Held-out set 2", "heldout_tasks_2"),
}


def load_code_cells(path):
    nb = json.load(open(path))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def find_cell(cells, marker):
    return next(c for c in cells if c.startswith(marker))


def print_pass_rates(results):
    per_task = defaultdict(list)
    for run in results["runs"]:
        for r in run:
            per_task[r["task_id"]].append(r["passed"])
    n_runs = results["config"]["num_runs"]
    print(f"\nPer-task pass rate over {n_runs} run(s)")
    for task_id, outcomes in per_task.items():
        print(f"  {sum(outcomes)}/{len(outcomes)}  {task_id}")
    per_run = [sum(r["passed"] for r in run) for run in results["runs"]]
    print(f"\nPassed per run: {per_run} of {results['config']['num_tasks']} tasks")


def mean_pass_rate(results):
    """Fraction of task attempts that passed, across every task and every run."""
    outcomes = [r["passed"] for run in results["runs"] for r in run]
    return sum(outcomes) / len(outcomes)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=("sanity", "single", "baseline", *HELDOUT_SETS))
    parser.add_argument("--runs", type=int, default=5, help="runs for baseline/heldout (default 5)")
    parser.add_argument("--notebook", default="Building_an_Eval.ipynb",
                        help="notebook holding the agent and graders (default: Building_an_Eval.ipynb)")
    parser.add_argument("--tasks-notebook", default=None,
                        help="notebook to read held-out tasks from (default: --notebook); "
                             "use with an older notebook to score a previous agent on the same tasks")
    parser.add_argument("--min-pass-rate", type=float, default=None, metavar="RATE",
                        help="exit 1 if the mean pass rate (0 to 1, across all tasks and runs) is below RATE; "
                             "for CI. Runs that error out count as failed. Ignored for the sanity stage")
    args = parser.parse_args()
    if args.min_pass_rate is not None and not 0 <= args.min_pass_rate <= 1:
        parser.error("--min-pass-rate must be between 0 and 1")

    cells = load_code_cells(args.notebook)
    ns = {"__name__": "__main__"}
    for marker in SETUP_CELLS:
        exec(compile(find_cell(cells, marker), marker[:20], "exec"), ns)

    if args.stage == "sanity":
        exec(compile(find_cell(cells, "# Grader sanity checks"), "sanity", "exec"), ns)
        return

    if args.stage in HELDOUT_SETS:
        marker, var = HELDOUT_SETS[args.stage]
        task_cells = load_code_cells(args.tasks_notebook or args.notebook)
        exec(compile(find_cell(task_cells, marker), args.stage, "exec"), ns)
        tasks, runs = ns[var], args.runs
    else:
        judge_cell = find_cell(cells, "# Add tasks that use the LLM-as-judge grader")
        exec(compile(judge_cell.split("# Run eval with both task sets")[0], "judge_tasks", "exec"), ns)
        tasks = ns["tasks"] + ns["llm_judge_tasks"]
        runs = 1 if args.stage == "single" else args.runs

    results = ns["run_eval"](ns["run_agent"], tasks, num_runs=runs)
    ns["save_results"](results)
    if runs == 1:
        ns["print_summary"](results)
    else:
        print_pass_rates(results)

    rate = mean_pass_rate(results)
    print(f"Mean pass rate: {rate:.1%}")
    if args.min_pass_rate is not None and rate < args.min_pass_rate:
        sys.exit(f"FAIL: mean pass rate {rate:.1%} is below the minimum {args.min_pass_rate:.1%}")


if __name__ == "__main__":
    main()
