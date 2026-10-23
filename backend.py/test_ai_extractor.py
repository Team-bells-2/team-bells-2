import json
import unittest

import httpx

from ai_extractor import extract_message


class AiExtractorTests(unittest.TestCase):
	def test_extracts_valid_structured_response(self) -> None:
		def handler(request: httpx.Request) -> httpx.Response:
			self.assertEqual(request.url.path, "/v1/chat/completions")
			self.assertEqual(request.headers["Authorization"], "Bearer test-key")
			request_data = json.loads(request.content)
			self.assertEqual(request_data["model"], "test-model")
			self.assertEqual(request_data["temperature"], 0)
			return httpx.Response(
				200,
				json={
					"choices": [
						{
							"message": {
								"content": json.dumps(
									{
										"status": "recorded",
										"entry": {
											"type": "sale",
											"item": "rice",
											"quantity": 2,
											"unit": "bags",
											"amount_ngn": 60000,
											"confidence": 0.95,
											"customer": None,
											"due_date": None,
										},
									}
								)
							}
						}
					]
				},
			)

		client = httpx.Client(transport=httpx.MockTransport(handler))
		result = extract_message(
			text="I sell 2 bags rice for 60k",
			context={"customers": []},
			api_key="test-key",
			base_url="https://provider.test/v1",
			model="test-model",
			client=client,
		)
		self.assertEqual(result["entry"]["amount_ngn"], 60000)
		self.assertEqual(result["status"], "recorded")
		client.close()

	def test_rejects_clarification_without_question(self) -> None:
		def handler(_: httpx.Request) -> httpx.Response:
			return httpx.Response(
				200,
				json={
					"choices": [
						{"message": {"content": json.dumps({"status": "needs_clarification", "missing_fields": ["amount_ngn"]})}}
					]
				},
			)

		with httpx.Client(transport=httpx.MockTransport(handler)) as client:
			with self.assertRaisesRegex(RuntimeError, "must include a question"):
				extract_message(text="I sell rice", api_key="test-key", client=client)

	def test_missing_key_fails_before_network_request(self) -> None:
		with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
			extract_message(text="I sell rice", api_key="")


if __name__ == "__main__":
	unittest.main()