# Evals · Build-Along

**Prepared for Partner Basecamp participants.** Not for reproduction or redistribution as training material — you're free to apply these patterns in your own client work.

## What you're building

An eval suite for `boutique`, a simple AI shopping assistant that looks up product prices and does math. The agent works — mostly. Your job is to figure out exactly where it breaks, why, and how to fix it using a systematic eval-driven approach.

## Main learning

How to build evals for AI agents: defining test tasks, writing graders, running the harness, and using results to make targeted improvements. You'll move from "try it and see" to a repeatable feedback loop you can point to with numbers before shipping to a customer.

---

## How to run

Work the exercise in the repo — don't copy code out of a chat window. No terminal setup needed: the **Setup — connect to Claude** cell at the top asks for your API key with a hidden prompt and shows a green **"✓ API key verified"** banner once you're connected. (If `ANTHROPIC_API_KEY` is already set in your environment, it's picked up automatically.)

### VS Code / Cursor (recommended)

1. **File → Open Folder** and select this folder.
2. Install the **Python** and **Jupyter** extensions if prompted.
3. Open [`Building_an_Eval.ipynb`](Building_an_Eval.ipynb) and pick a **Python 3** kernel — run cells with **Shift+Enter**, or **Run All** (the chat cell starts an interactive session automatically; type `quit` to move past it, or set `INTERACTIVE_CHAT = False` in that cell first to skip straight to the eval sections).

### Claude Code (CLI)

`cd` into this folder and pair with Claude Code on the exercise:

```bash
cd day2/01_evals
claude                          # work the exercise with Claude Code as your pair
```

### Claude Desktop

Keep it open alongside as your AI pair — ask it to explain a cell, debug an error, or suggest the next change while you edit.

The setup cell verifies your key with a real API call — green banner means you're connected. Never paste a key into a cell.

### From a shell (no Jupyter)

[`run_eval.py`](run_eval.py) runs the notebook's cells headless and executes one stage. Run it from this folder with the project venv:

```bash
.venv/bin/python run_eval.py sanity              # grader sanity checks only
.venv/bin/python run_eval.py single              # one run of the 32-task suite
.venv/bin/python run_eval.py baseline --runs 5   # 5 runs, per-task pass rates
.venv/bin/python run_eval.py heldout --runs 5    # the 10 held-out tasks
.venv/bin/python run_eval.py heldout2 --runs 5   # 8 negative and adversarial held-out tasks
.venv/bin/python run_eval.py --help              # all options
```

Your key comes from `ANTHROPIC_API_KEY` or a `.env` file, same as the notebook. Each run saves a JSON file to `eval_results/`.
