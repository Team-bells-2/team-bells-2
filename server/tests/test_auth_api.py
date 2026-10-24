"""Session expiry, logout and the optional PIN login (NFR-7, FR-C5; BR-O3, BR-O4).
Run: cd server && python -m unittest discover -s tests -t ."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.onboarding.models import Trader, TraderSession
from tests.support import ApiTestCase

PHONE = "08031234567"
ONBOARDING = {
    "name": "Ada Obi", "phone": PHONE, "business_name": "Ada Foods", "sector": "foodstuff", "location_name": "Mile 12",
}


class AuthTest(ApiTestCase):
    def signup(self, **extra: object) -> dict[str, str]:
        response = self.client.post("/onboarding", json={**ONBOARDING, **extra})
        self.assertEqual(response.status_code, 201, response.text)
        return {"Authorization": f"Bearer {response.json()['token']}"}

    def login(self, pin: str, phone: str = PHONE):
        return self.client.post("/auth/login", json={"phone": phone, "pin": pin})

    def test_new_sessions_expire_after_the_ttl(self) -> None:
        self.signup()
        with self.Session() as db:
            session = db.scalar(select(TraderSession))
            assert session is not None and session.expires_at is not None
            expires = session.expires_at.replace(tzinfo=UTC) if session.expires_at.tzinfo is None else session.expires_at
        self.assertAlmostEqual((expires - datetime.now(UTC)).total_seconds(), timedelta(days=30).total_seconds(), delta=60)

    def test_expired_session_is_401(self) -> None:
        headers = self.signup()
        with self.Session() as db:
            db.execute(update(TraderSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
            db.commit()
        response = self.client.get("/profile", headers=headers)
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (401, "invalid_token"))

    def test_session_without_expiry_still_works(self) -> None:
        headers = self.signup()
        with self.Session() as db:
            db.execute(update(TraderSession).values(expires_at=None))
            db.commit()
        self.assertEqual(self.client.get("/profile", headers=headers).status_code, 200)

    def test_logout_ends_only_this_session(self) -> None:
        first = self.signup(pin="1234")
        second = {"Authorization": f"Bearer {self.login('1234').json()['token']}"}
        self.assertEqual(self.client.post("/auth/logout", headers=first).status_code, 204)
        self.assertEqual(self.client.get("/profile", headers=first).status_code, 401)
        self.assertEqual(self.client.get("/profile", headers=second).status_code, 200)

    def test_login_with_pin_returns_a_working_token(self) -> None:
        self.signup(pin="1234")
        body = self.login("1234").json()
        self.assertEqual(body["trader"]["phone"], PHONE)
        self.assertEqual(self.client.get("/profile", headers={"Authorization": f"Bearer {body['token']}"}).status_code, 200)

    def test_pin_is_stored_hashed(self) -> None:
        self.signup(pin="1234")
        with self.Session() as db:
            stored = db.scalar(select(Trader.pin_hash))
        self.assertTrue(stored and stored.startswith("scrypt$") and "1234" not in stored)

    def test_wrong_pin_unknown_phone_and_no_pin_look_the_same(self) -> None:
        self.signup(pin="1234")
        self.client.post("/onboarding", json={**ONBOARDING, "phone": "08030000002"})  # no PIN
        for response in (self.login("9999"), self.login("1234", phone="08099999999"), self.login("1234", phone="08030000002")):
            with self.subTest(response=response):
                self.assertEqual(
                    response.json(), {"error": {"code": "invalid_credentials", "message": "Phone number or PIN is wrong."}}
                )

    def test_five_wrong_pins_lock_the_account(self) -> None:
        self.signup(pin="1234")
        for _ in range(5):
            self.assertEqual(self.login("9999").status_code, 401)
        locked = self.login("1234")
        self.assertEqual((locked.status_code, locked.json()["error"]["code"]), (429, "account_locked"))
        with self.Session() as db:
            db.execute(update(Trader).values(locked_until=datetime.now(UTC) - timedelta(seconds=1)))
            db.commit()
        self.assertEqual(self.login("1234").status_code, 200)

    def test_pin_format_is_checked(self) -> None:
        response = self.client.post("/onboarding", json={**ONBOARDING, "pin": "12ab"})
        self.assertEqual(response.status_code, 422)

    def test_first_pin_is_set_without_a_current_pin(self) -> None:
        headers = self.signup()
        self.assertEqual(self.client.post("/auth/change-pin", headers=headers, json={"new_pin": "4321"}).status_code, 204)
        self.assertEqual(self.login("4321").status_code, 200)

    def test_changing_a_pin_needs_the_current_one(self) -> None:
        headers = self.signup(pin="1234")
        wrong = self.client.post("/auth/change-pin", headers=headers, json={"current_pin": "0000", "new_pin": "4321"})
        self.assertEqual(wrong.status_code, 401)
        missing = self.client.post("/auth/change-pin", headers=headers, json={"new_pin": "4321"})
        self.assertEqual(missing.status_code, 401)
        ok = self.client.post("/auth/change-pin", headers=headers, json={"current_pin": "1234", "new_pin": "4321"})
        self.assertEqual(ok.status_code, 204)
        self.assertEqual((self.login("1234").status_code, self.login("4321").status_code), (401, 200))
