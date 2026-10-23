from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = Path(__file__).with_name("merchant_messages.json")
Adapter = Callable[..., dict[str, Any]]


def load_cases(path: Path) -> list[dict[str, Any]]:
	with path.open(encoding="utf-8") as cases_file:
		cases = json.load(cases_file)
	if not isinstance(cases, list):
		raise ValueError("Evaluation file must contain a JSON array.")
	return cases


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
	errors = []
	seen_ids = set()
	required_categories = {
		"sale",
		"credit_sale",
		"expense",
		"payment",
		"stock_in",
		"customer_alias",
		"ambiguity",
		"clarification",
		"correction",
	}
	found_categories = set()

	for index, case in enumerate(cases):
		prefix = f"case[{index}]"
		for key in ("id", "category", "language", "text", "context", "expected"):
			if key not in case:
				errors.append(f"{prefix}: missing required field '{key}'")
		if "id" in case:
			if case["id"] in seen_ids:
				errors.append(f"{prefix}: duplicate id '{case['id']}'")
			seen_ids.add(case["id"])
		if "category" in case:
			found_categories.add(case["category"])
		if not isinstance(case.get("text"), str) or not case["text"].strip():
			errors.append(f"{prefix}: text must be a non-empty string")
		if not isinstance(case.get("expected"), dict):
			errors.append(f"{prefix}: expected must be an object")

	missing_categories = required_categories - found_categories
	if missing_categories:
		errors.append("missing categories: " + ", ".join(sorted(missing_categories)))
	if not cases:
		errors.append("evaluation set is empty")
	return errors


def compare_expected(expected: Any, actual: Any, path: str = "output") -> list[str]:
	if isinstance(expected, dict):
		if not isinstance(actual, dict):
			return [f"{path}: expected object, got {type(actual).__name__}"]
		errors = []
		for key, expected_value in expected.items():
			if key not in actual:
				errors.append(f"{path}.{key}: missing from actual output")
			else:
				errors.extend(compare_expected(expected_value, actual[key], f"{path}.{key}"))
		return errors
	if expected != actual:
		return [f"{path}: expected {expected!r}, got {actual!r}"]
	return []


def evaluate(cases: list[dict[str, Any]], adapter: Adapter) -> list[dict[str, Any]]:
	results = []
	for case in cases:
		try:
			actual = adapter(text=case["text"], context=case.get("context", {}))
			if not isinstance(actual, dict):
				raise TypeError("extractor must return a dictionary")
			failures = compare_expected(case["expected"], actual)
			if actual.get("status") == "needs_clarification":
				question = actual.get("question")
				if not isinstance(question, str) or not question.strip():
					failures.append("output.question: clarification response must include a non-empty question")
			results.append({"id": case["id"], "category": case["category"], "actual": actual, "failures": failures})
		except Exception as error:
			results.append({
				"id": case["id"],
				"category": case["category"],
				"actual": None,
				"failures": [f"extractor raised {type(error).__name__}: {error}"],
			})
	return results


def load_adapter(specification: str) -> Adapter:
	if ":" not in specification:
		raise ValueError("Adapter must use module:function format, e.g. backend.ai:extract_message")
	module_name, function_name = specification.split(":", maxsplit=1)
	sys.path.insert(0, str(ROOT))
	sys.path.insert(0, str(ROOT / "backend.py"))
	module = importlib.import_module(module_name)
	adapter = getattr(module, function_name, None)
	if not callable(adapter):
		raise ValueError(f"Adapter '{specification}' is not a callable function")
	return adapter


def print_report(cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> None:
	passed = sum(not result["failures"] for result in results)
	category_results: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for result in results:
		category_results[result["category"]].append(result)

	print(f"Overall: {passed}/{len(results)} passed")
	for category in sorted(category_results):
		category_cases = category_results[category]
		category_passed = sum(not result["failures"] for result in category_cases)
		print(f"{category}: {category_passed}/{len(category_cases)} passed")

	for result in results:
		if result["failures"]:
			case = next(case for case in cases if case["id"] == result["id"])
			print(f"\nFAIL {result['id']} [{result['category']}] {case['text']}")
			for failure in result["failures"]:
				print(f"  - {failure}")
			print("  actual: " + json.dumps(result["actual"], ensure_ascii=False, sort_keys=True))


def main() -> int:
	parser = argparse.ArgumentParser(description="Evaluate MerchantPal message extraction against a small golden test set.")
	parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="Path to the JSON evaluation set")
	parser.add_argument("--adapter", help="Extractor callable as module:function")
	parser.add_argument("--validate-only", action="store_true", help="Validate cases and coverage without running an extractor")
	args = parser.parse_args()

	try:
		cases = load_cases(args.cases)
	except (OSError, json.JSONDecodeError, ValueError) as error:
		print(f"Could not load evaluation cases: {error}", file=sys.stderr)
		return 2

	case_errors = validate_cases(cases)
	if case_errors:
		for error in case_errors:
			print(f"Invalid evaluation set: {error}", file=sys.stderr)
		return 2
	if args.validate_only:
		print(f"Evaluation set valid: {len(cases)} cases across {len({case['category'] for case in cases})} categories")
		return 0
	if not args.adapter:
		parser.error("--adapter is required unless --validate-only is used")

	try:
		adapter = load_adapter(args.adapter)
	except (ImportError, AttributeError, ValueError) as error:
		print(f"Could not load extractor: {error}", file=sys.stderr)
		return 2

	results = evaluate(cases, adapter)
	print_report(cases, results)
	return 0 if all(not result["failures"] for result in results) else 1


if __name__ == "__main__":
	raise SystemExit(main())