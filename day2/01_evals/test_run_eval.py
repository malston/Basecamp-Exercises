#!/usr/bin/env python3
"""Offline tests for run_eval.py and the eval's task definitions. No API calls.

Use when: before running the paid eval, to catch a broken CI gate, a renamed
notebook cell, or a malformed task.

Usage (from this folder):  python -m unittest test_run_eval -v
"""
import contextlib
import io
import unittest

import run_eval

NOTEBOOK = "Building_an_Eval.ipynb"
VALID_TOOLS = {"get_product", "calculate"}


def results_with(*per_run):
    """Results dict where each argument is one run's list of passed flags."""
    return {"runs": [[{"passed": p} for p in run] for run in per_run]}


class MeanPassRateTest(unittest.TestCase):
    def test_all_pass(self):
        self.assertEqual(run_eval.mean_pass_rate(results_with([True, True])), 1.0)

    def test_mixed_runs(self):
        self.assertEqual(run_eval.mean_pass_rate(results_with([True, False], [False, False])), 0.25)

    def test_no_attempts_is_an_error(self):
        with self.assertRaises(ValueError):
            run_eval.mean_pass_rate({"runs": []})
        with self.assertRaises(ValueError):
            run_eval.mean_pass_rate({"runs": [[]]})


class ErroredAttemptsTest(unittest.TestCase):
    def test_counts_only_attempts_with_an_error(self):
        results = {"runs": [[{"passed": False, "error": "boom"}, {"passed": False}, {"passed": True}]]}
        self.assertEqual(run_eval.errored_attempts(results), 1)


class NotebookStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = run_eval.load_code_cells(NOTEBOOK)

    def test_every_marker_matches_exactly_one_cell(self):
        markers = list(run_eval.SETUP_CELLS) + [m for m, _ in run_eval.HELDOUT_SETS.values()] + [
            "# Grader sanity checks",
            "# Add tasks that use the LLM-as-judge grader",
        ]
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertEqual(sum(c.startswith(marker) for c in self.cells), 1)

    def test_judge_tasks_cell_has_the_split_marker(self):
        cell = run_eval.find_cell(self.cells, "# Add tasks that use the LLM-as-judge grader")
        self.assertIn("# Run eval with both task sets", cell)


class TaskDefinitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cells = run_eval.load_code_cells(NOTEBOOK)
        ns = {"_model": lambda name: name, "client": None}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(run_eval.find_cell(cells, "# ── Graders"), ns)
            exec(run_eval.find_cell(cells, "# ✏️ YOUR TURN"), ns)
            exec(run_eval.find_cell(cells, "# Implement the LLM-as-judge grader"), ns)
            judge_cell = run_eval.find_cell(cells, "# Add tasks that use the LLM-as-judge grader")
            exec(judge_cell.split("# Run eval with both task sets")[0], ns)
            for marker, _ in run_eval.HELDOUT_SETS.values():
                exec(run_eval.find_cell(cells, marker), ns)
        cls.ns = ns
        cls.all_tasks = ns["tasks"] + ns["llm_judge_tasks"] + ns["heldout_tasks"] + ns["heldout_tasks_2"]
        sanity = run_eval.find_cell(cells, "# Grader sanity checks")
        exec(sanity.split("failures = 0")[0], ns)

    def test_task_counts(self):
        self.assertEqual(len(self.ns["tasks"]) + len(self.ns["llm_judge_tasks"]), 32)
        self.assertEqual(len(self.ns["heldout_tasks"]), 10)
        self.assertEqual(len(self.ns["heldout_tasks_2"]), 8)

    def test_ids_and_queries_are_unique(self):
        ids = [t["id"] for t in self.all_tasks]
        queries = [t["query"] for t in self.all_tasks]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(queries), len(set(queries)))

    def test_every_task_has_graders_with_checks(self):
        for task in self.all_tasks:
            with self.subTest(task=task["id"]):
                self.assertTrue(task["graders"])
                for grader in task["graders"]:
                    self.assertIn(grader["type"], self.ns["GRADER_REGISTRY"])
                    self.assertTrue(grader["checks"])

    def test_tool_use_checks_name_real_tools(self):
        for task in self.all_tasks:
            for grader in task["graders"]:
                if grader["type"] == "tool_use":
                    for check in grader["checks"]:
                        with self.subTest(task=task["id"]):
                            self.assertIn(check["tool_name"], VALID_TOOLS)

    def test_deterministic_grader_sanity_cases(self):
        registry = self.ns["GRADER_REGISTRY"]
        for grader_type, check, text, expected, *calls in self.ns["GRADER_CASES"]:
            if grader_type == "llm_judge":
                continue
            with self.subTest(grader=grader_type, text=text):
                got = registry[grader_type](self.ns["_fake"](text, *calls), check, {})["score"]
                self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
