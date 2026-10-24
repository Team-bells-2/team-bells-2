"""The eval set and runner (FR-S18, FR-S19). The score itself is reported by `make eval`, not asserted here.
Run: cd server && python -m unittest discover -s tests -t ."""

import json
import unittest
from collections import Counter

import tests.support  # noqa: F401  (test settings first)
from eval.run_eval import CASES_FILE, run


class EvalCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))

    def test_forty_unique_cases(self) -> None:
        self.assertEqual(len(self.cases), 40)
        self.assertEqual(len({case["id"] for case in self.cases}), 40)

    def test_coverage_required_by_fr_s19(self) -> None:
        categories = Counter(case["category"] for case in self.cases)
        for category in ("sale", "credit_sale", "payment_received", "expense", "correction", "clarify"):
            with self.subTest(category=category):
                self.assertGreater(categories[category], 0)
        self.assertGreaterEqual(sum(1 for case in self.cases if case.get("hard")), 10)

    def test_every_case_has_an_expected_status(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertIn(case["expected"]["status"], {"saved", "corrected", "clarify", "fallback"})

    def test_runner_scores_every_case_offline(self) -> None:
        report = run(live=False)
        self.assertEqual((report["total"], len(report["results"])), (40, 40))
        self.assertTrue(all(isinstance(result["ok"], bool) for result in report["results"]))
