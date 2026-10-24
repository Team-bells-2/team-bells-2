"""POST /messages end to end with a fake LLM and transcriber (FR-S1 to S8, NFR-1, NFR-5).
Run: cd server && python -m unittest discover -s tests -t ."""

from decimal import Decimal

from sqlalchemy import func, select

from app.ledger.models import Entry, ProcessedMessage
from app.shared.Infrastructure.llm.client import LLMError
from tests.support import ApiTestCase, interpretation


class MessagesApiTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def entries(self) -> int:
        with self.Session() as db:
            return db.scalar(select(func.count(Entry.id))) or 0

    def test_amount_is_parsed_in_code_and_model_figures_or_stock_actions_are_ignored(self) -> None:
        rice = self.add_stock(self.trader_id, "Rice", "10")
        reply = interpretation(
            type="credit_sale", item="rice", quantity=2, unit="bag", amount_text="sixty k", customer="Mama Ngozi",
            amount_ngn=999999, action={"type": "stock_in", "item": "rice", "quantity": 500},
        )
        body = self.send(self.headers, "Mama Ngozi carry 2 bag rice sixty k", "m1", reply).json()
        self.assertEqual((body["status"], body["entry"]["amount_ngn"]), ("saved", 60000))
        self.assertEqual(body["message"], "Saved: credit sale of 2 bag rice to Mama Ngozi for ₦60,000.")
        self.assertEqual(self.on_hand(rice), Decimal(8))

    def test_retry_with_same_client_message_id_replays_without_a_second_entry(self) -> None:
        first = self.send(self.headers, "sold rice 10k", "m1", interpretation(type="sale", amount_text="10k")).json()
        second = self.send(self.headers, "sold rice 10k", "m1").json()
        self.assertEqual(first, second)
        self.assertEqual((self.entries(), self.llm.calls), (1, 1))

    def test_invalid_model_output_is_retried_once(self) -> None:
        self.llm.queue = [{"intent": "entry"}, interpretation(type="sale", amount_text="2.5k")]
        body = self.send(self.headers, "sold 1 bag 2.5k", "m1").json()
        self.assertEqual((body["status"], body["entry"]["amount_ngn"]), ("saved", 2500))

    def test_invalid_output_twice_asks_to_repeat_and_writes_nothing(self) -> None:
        self.llm.queue = [{"bad": 1}, {"intent": "maybe"}]
        body = self.send(self.headers, "???", "m1").json()
        self.assertEqual(body, {**body, "status": "clarify", "message": "Sorry, I didn't catch that. Can you say it again?"})
        self.assertEqual(self.entries(), 0)

    def test_low_confidence_is_confirmed_before_saving(self) -> None:
        body = self.send(
            self.headers, "rice one bag 10k abi", "m1",
            interpretation(type="sale", item="rice", quantity=1, unit="bag", amount_text="10k", confidence=0.4),
        ).json()
        self.assertEqual((body["status"], body["message"]), ("clarify", "Just to confirm: sale of rice, ₦10,000?"))
        self.assertEqual(self.entries(), 0)
        body = self.send(self.headers, "yes", "m2", interpretation(confidence=0.95)).json()
        self.assertEqual((body["status"], body["entry"]["raw_text"]), ("saved", "rice one bag 10k abi | yes"))

    def test_off_topic_message_gets_fallback_and_no_entry(self) -> None:
        body = self.send(self.headers, "how far", "m1", {"intent": "unknown", "confidence": 0.9}).json()
        self.assertEqual(body["status"], "fallback")
        self.assertEqual(self.entries(), 0)

    def test_unparseable_amount_asks_how_much(self) -> None:
        body = self.send(
            self.headers, "sold rice for plenty money", "m1", interpretation(type="sale", amount_text="plenty money")
        ).json()
        self.assertEqual((body["status"], body["message"]), ("clarify", "How much was it?"))

    def test_correction_intent_updates_last_entry(self) -> None:
        saved = self.send(self.headers, "transport 40k", "m1", interpretation(type="expense", item="transport", amount_text="40k")).json()
        body = self.send(self.headers, "no be 45k", "m2", {"intent": "correction", "confidence": 0.9, "amount_text": "45k"}).json()
        self.assertEqual((body["status"], body["entry"]["id"], body["entry"]["amount_ngn"]), ("corrected", saved["entry"]["id"], 45000))

    def test_provider_down_is_503_and_the_same_id_works_later(self) -> None:
        response = self.send(self.headers, "sold rice 3k", "m1", LLMError("down"))
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (503, "ai_unavailable"))
        with self.Session() as db:
            self.assertIsNone(db.get(ProcessedMessage, (self.trader_id, "m1")))
        body = self.send(self.headers, "sold rice 3k", "m1", interpretation(type="sale", amount_text="3k")).json()
        self.assertEqual(body["status"], "saved")

    def test_missing_client_message_id_is_422(self) -> None:
        response = self.client.post("/messages", headers=self.headers, json={"text": "hi"})
        self.assertEqual(response.json()["error"]["message"], "client_message_id: Field required")

    def test_no_token_is_401(self) -> None:
        response = self.client.post("/messages", json={"text": "hi", "client_message_id": "m1"})
        self.assertEqual(response.status_code, 401)


class VoiceMessagesTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def voice(self, content_type: str, message_id: str, data: bytes = b"audio", headers: dict[str, str] | None = None):
        return self.client.post(
            "/messages",
            headers=self.headers if headers is None else headers,
            files={"audio": ("note", data, content_type)},
            data={"client_message_id": message_id},
        )

    def test_voice_note_is_transcribed_and_transcript_is_raw_text(self) -> None:
        self.llm.queue.append(interpretation(type="sale", item="rice", quantity=1, unit="bag", amount_text="ten k"))
        body = self.voice("audio/m4a", "v1").json()
        self.assertEqual((body["status"], body["transcript"]), ("saved", self.stt.text))
        self.assertEqual((body["entry"]["raw_text"], body["entry"]["amount_ngn"]), (self.stt.text, 10000))

    def test_generic_content_type_is_rejected(self) -> None:
        self.assertEqual(self.voice("application/octet-stream", "v1").status_code, 415)

    def test_transcription_failure_is_502_and_writes_nothing(self) -> None:
        self.stt.fail = True
        response = self.voice("audio/wav", "v1")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (502, "transcription_failed"))
        with self.Session() as db:
            self.assertIsNone(db.get(ProcessedMessage, (self.trader_id, "v1")))

    def test_upload_over_the_limit_is_413(self) -> None:
        self.assertEqual(self.voice("audio/wav", "v1", data=b"x" * (1024 * 1024 + 1)).status_code, 413)

    def test_voice_without_token_is_401(self) -> None:
        self.assertEqual(self.voice("audio/wav", "v1", headers={}).status_code, 401)
