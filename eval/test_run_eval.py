import unittest
from pathlib import Path

from run_eval import evaluate, load_cases, validate_cases


class EvaluationRunnerTests(unittest.TestCase):
	def setUp(self) -> None:
		self.cases = load_cases(Path(__file__).with_name("merchant_messages.json"))

	def test_golden_set_has_required_case_coverage(self) -> None:
		self.assertEqual(validate_cases(self.cases), [])

	def test_runner_checks_expected_fields_and_clarification_question(self) -> None:
		def expected_output_adapter(**kwargs: dict) -> dict:
			case = next(case for case in self.cases if case["text"] == kwargs["text"])
			self.assertIsInstance(kwargs["context"], dict)
			output = case["expected"].copy()
			if output["status"] == "needs_clarification":
				output["question"] = "Which customer do you mean?"
			return output

		results = evaluate(self.cases, expected_output_adapter)
		self.assertEqual(len(results), len(self.cases))
		self.assertTrue(all(not result["failures"] for result in results))

	def test_runner_reports_exact_field_mismatch(self) -> None:
		case = self.cases[0]
		results = evaluate([case], lambda **_: {"status": "recorded", "entry": {"amount_ngn": 10}})

		self.assertTrue(results[0]["failures"])
		self.assertIn("output.entry.type", " ".join(results[0]["failures"]))

	def test_clarification_requires_a_question(self) -> None:
		case = next(case for case in self.cases if case["expected"]["status"] == "needs_clarification")
		results = evaluate([case], lambda **_: case["expected"])

		self.assertIn("output.question", " ".join(results[0]["failures"]))


if __name__ == "__main__":
	unittest.main()