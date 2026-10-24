"""Due dates computed in code, and overdue customers (FR-S12; BR-A2, BR-C1).
Run: cd server && python -m unittest discover -s tests -t ."""

from datetime import date, datetime, timedelta

from sqlalchemy import update

from app.ledger.models import Entry
from app.ledger.services import resolve_due_date
from app.shared.periods import LAGOS
from tests.support import ApiTestCase, interpretation

WEDNESDAY = date(2026, 10, 28)


class ResolveDueDateTest(ApiTestCase):
    def test_phrases(self) -> None:
        cases = {
            "Friday": date(2026, 10, 30),
            "she go pay friday": date(2026, 10, 30),
            "Monday": date(2026, 11, 2),
            "Wednesday": date(2026, 11, 4),  # same weekday as today -> a week ahead
            "tomorrow": date(2026, 10, 29),
            "tmrw": date(2026, 10, 29),
            "next tomorrow": date(2026, 10, 30),
            "next week": date(2026, 11, 4),
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(resolve_due_date(phrase, WEDNESDAY), expected)

    def test_unrecognised_phrase_gives_no_date(self) -> None:
        self.assertIsNone(resolve_due_date("when she get money", WEDNESDAY))


class DueDateApiTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def test_credit_sale_due_friday_is_saved_as_the_coming_friday(self) -> None:
        today = datetime.now(LAGOS).date()
        expected = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
        body = self.send(
            self.headers, "Mama Ngozi carry rice 60k, she go pay Friday", "m1",
            interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k", due_text="Friday"),
        ).json()
        self.assertEqual(body["entry"]["due_date"], expected.isoformat())
        self.assertIn(f"due {expected:%a %d %b}", body["message"])

    def test_model_dates_are_ignored(self) -> None:
        body = self.send(
            self.headers, "Mama Ngozi carry rice 60k", "m1",
            interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k", due_date="2030-01-01"),
        ).json()
        self.assertIsNone(body["entry"]["due_date"])

    def test_only_credit_sales_get_a_due_date(self) -> None:
        body = self.send(
            self.headers, "sold rice 10k tomorrow", "m1", interpretation(type="sale", amount_text="10k", due_text="tomorrow")
        ).json()
        self.assertIsNone(body["entry"]["due_date"])

    def test_customer_is_overdue_while_owing_past_the_due_date(self) -> None:
        self.send(
            self.headers, "Mama Ngozi carry rice 60k", "m1",
            interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k", due_text="tomorrow"),
        )
        self.assertFalse(self.client.get("/customers", headers=self.headers).json()[0]["overdue"])
        with self.Session() as db:
            db.execute(update(Entry).values(due_date=datetime.now(LAGOS).date() - timedelta(days=1)))
            db.commit()
        self.assertTrue(self.client.get("/customers", headers=self.headers).json()[0]["overdue"])
        self.send(
            self.headers, "Mama Ngozi don pay 60k", "m2",
            interpretation(type="payment_received", customer="Mama Ngozi", amount_text="60k"),
        )
        self.assertFalse(self.client.get("/customers", headers=self.headers).json()[0]["overdue"])  # paid up
