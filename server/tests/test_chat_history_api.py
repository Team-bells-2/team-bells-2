"""GET /messages/history: the assistant chat per trader, restored by the app after a restart.
Run: cd server && python -m unittest discover -s tests -t ."""

from app.shared.Infrastructure.llm.client import LLMError
from tests.support import ApiTestCase, interpretation


class ChatHistoryApiTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def history(self, query: str = "", headers: dict[str, str] | None = None) -> dict:
        response = self.client.get(f"/messages/history{query}", headers=self.headers if headers is None else headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def turns(self) -> list[tuple[str, str]]:
        return [(m["role"], m["text"]) for m in self.history()["messages"]]

    def test_empty_for_a_new_trader(self) -> None:
        self.assertEqual(self.history(), {"messages": [], "has_more": False})

    def test_saved_clarify_and_fallback_turns_are_stored_oldest_first(self) -> None:
        saved = self.send(self.headers, "sold rice 10k", "m1", interpretation(type="sale", item="rice", amount_text="10k")).json()
        clarify = self.send(self.headers, "sold rice for plenty money", "m2", interpretation(type="sale", amount_text="plenty money")).json()
        fallback = self.send(self.headers, "how far", "m3", {"intent": "unknown", "confidence": 0.9}).json()
        self.assertEqual((saved["status"], clarify["status"], fallback["status"]), ("saved", "clarify", "fallback"))

        self.assertEqual(
            self.turns(),
            [
                ("trader", "sold rice 10k"),
                ("assistant", saved["message"]),
                ("trader", "sold rice for plenty money"),
                ("assistant", "How much was it?"),
                ("trader", "how far"),
                ("assistant", fallback["message"]),
            ],
        )

    def test_assistant_reply_links_the_saved_entry(self) -> None:
        saved = self.send(self.headers, "transport 40k", "m1", interpretation(type="expense", item="transport", amount_text="40k")).json()
        messages = self.history()["messages"]
        self.assertEqual([m["entry_id"] for m in messages], [None, saved["entry"]["id"]])
        self.assertLess(messages[0]["id"], messages[1]["id"])
        self.assertIn("created_at", messages[0])

    def test_retry_with_same_client_message_id_is_stored_once(self) -> None:
        self.send(self.headers, "transport 40k", "m1", interpretation(type="expense", item="transport", amount_text="40k"))
        self.send(self.headers, "transport 40k", "m1")  # replayed reply, no model call
        self.assertEqual(len(self.history()["messages"]), 2)

    def test_failed_message_is_not_stored(self) -> None:
        response = self.send(self.headers, "how far", "m1", LLMError("down"))  # the rules can't read it either
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(self.history()["messages"], [])

    def test_ask_turns_are_stored(self) -> None:
        answer = self.client.post("/ask", headers=self.headers, json={"question": "Who owes me?"}).json()["answer"]
        self.assertEqual(self.turns(), [("trader", "Who owes me?"), ("assistant", answer)])

    def test_voice_turn_stores_the_transcript(self) -> None:
        self.llm.queue.append(interpretation(type="sale", item="rice", quantity=1, unit="bag", amount_text="ten k"))
        response = self.client.post(
            "/messages",
            headers=self.headers,
            files={"audio": ("note", b"audio", "audio/m4a")},
            data={"client_message_id": "v1"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.turns()[0], ("trader", self.stt.text))

    def test_paging_returns_newest_page_then_older(self) -> None:
        for i in range(3):
            self.send(self.headers, f"transport {i + 1}k", f"m{i}", interpretation(type="expense", item="transport", amount_text=f"{i + 1}k"))
        page = self.history("?limit=4")
        self.assertTrue(page["has_more"])
        self.assertEqual([m["text"] for m in page["messages"] if m["role"] == "trader"], ["transport 2k", "transport 3k"])
        older = self.history(f"?limit=4&before_id={page['messages'][0]['id']}")
        self.assertFalse(older["has_more"])
        self.assertEqual([m["text"] for m in older["messages"]], ["transport 1k", self.history()["messages"][1]["text"]])

    def test_each_trader_sees_only_their_own_chat(self) -> None:
        self.send(self.headers, "transport 40k", "m1", interpretation(type="expense", item="transport", amount_text="40k"))
        _, other = self.onboard(phone="08039999999")
        self.assertEqual(self.history(headers=other)["messages"], [])

    def test_requires_a_token(self) -> None:
        self.assertEqual(self.client.get("/messages/history").status_code, 401)
