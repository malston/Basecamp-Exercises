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

Credentials: ANTHROPIC_API_KEY in the environment or in a .env file, same as the notebook.
"""
import argparse
import json
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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=("sanity", "single", "baseline", "heldout"))
    parser.add_argument("--runs", type=int, default=5, help="runs for baseline/heldout (default 5)")
    parser.add_argument("--notebook", default="Building_an_Eval.ipynb",
                        help="notebook holding the agent and graders (default: Building_an_Eval.ipynb)")
    parser.add_argument("--tasks-notebook", default=None,
                        help="notebook to read held-out tasks from (default: --notebook); "
                             "use with an older notebook to score a previous agent on the same tasks")
    args = parser.parse_args()

    cells = load_code_cells(args.notebook)
    ns = {"__name__": "__main__"}
    for marker in SETUP_CELLS:
        exec(compile(find_cell(cells, marker), marker[:20], "exec"), ns)

    if args.stage == "sanity":
        exec(compile(find_cell(cells, "# Grader sanity checks"), "sanity", "exec"), ns)
        return

    if args.stage == "heldout":
        task_cells = load_code_cells(args.tasks_notebook or args.notebook)
        exec(compile(find_cell(task_cells, "# Held-out tasks"), "heldout", "exec"), ns)
        tasks, runs = ns["heldout_tasks"], args.runs
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


if __name__ == "__main__":
    main()
