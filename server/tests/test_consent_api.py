"""Consent-gated agent access (FR-S13 to S17, NFR-6; BR-K1 to K8).
Run: cd server && python -m unittest discover -s tests -t ."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.consent.models import AccessLog, AccessToken
from tests.support import ApiTestCase, interpretation

PHONE = "08031234567"
REQUEST = {
    "trader_phone": PHONE,
    "agent_name": "QuickLoan agent",
    "purpose": "Check credit readiness for a ₦200,000 loan",
    "data_scopes": ["sales_total", "total_owed", "active_days"],
}


class ConsentTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard(phone=PHONE)
        self.send(self.headers, "Mama Ngozi carry rice 60k credit", "e1", interpretation(type="credit_sale", customer="Mama Ngozi", amount_text="60k"))
        self.send(self.headers, "Mama Ngozi don pay 30k", "e2", interpretation(type="payment_received", customer="Mama Ngozi", amount_text="30k"))
        self.send(self.headers, "sold beans 50k", "e3", interpretation(type="sale", item="beans", amount_text="50k"))

    def request_access(self, **overrides: object) -> dict:
        response = self.client.post("/access-requests", json={**REQUEST, **overrides})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def poll(self, created: dict):
        return self.client.get(
            f"/access-requests/{created['request_id']}/status", headers={"X-Claim-Secret": created["claim_secret"]}
        )

    def approve(self, request_id: int, approve: bool = True):
        return self.client.post(f"/access-requests/{request_id}/approve", headers=self.headers, json={"approve": approve})

    def approved_token(self, **overrides: object) -> tuple[int, str]:
        created = self.request_access(**overrides)
        self.approve(created["request_id"])
        return created["request_id"], self.poll(created).json()["access_token"]

    def summary(self, token: str | None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.get("/agent/summary", headers=headers)

    def log_results(self) -> list[str]:
        with self.Session() as db:
            return list(db.scalars(select(AccessLog.result).order_by(AccessLog.id)).all())

    def test_request_without_purpose_or_scopes_is_422(self) -> None:
        for missing in ("purpose", "data_scopes"):
            with self.subTest(missing=missing):
                body = {key: value for key, value in REQUEST.items() if key != missing}
                self.assertEqual(self.client.post("/access-requests", json=body).status_code, 422)
        self.assertEqual(self.client.post("/access-requests", json={**REQUEST, "data_scopes": []}).status_code, 422)

    def test_unknown_phone_is_404(self) -> None:
        response = self.client.post("/access-requests", json={**REQUEST, "trader_phone": "08099999999"})
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (404, "trader_not_found"))

    def test_app_sees_the_pending_request_with_a_prompt(self) -> None:
        self.request_access(data_scopes=["sales_total", "total_owed"])
        (pending,) = self.client.get("/access-requests?status=pending", headers=self.headers).json()
        self.assertEqual(pending["prompt"], "QuickLoan agent wants to see your sales total, total owed for 30 days. Approve?")
        self.assertEqual([row["result"] for row in pending["log"]], ["requested"])

    def test_token_is_collected_once_after_approval_and_stored_hashed(self) -> None:
        created = self.request_access()
        self.assertNotIn("access_token", self.poll(created).json())  # still pending
        self.approve(created["request_id"])
        first = self.poll(created).json()
        self.assertEqual((first["status"], first["token_type"]), ("approved", "bearer"))
        second = self.poll(created).json()
        self.assertNotIn("access_token", second)
        self.assertTrue(second["token_already_collected"])
        with self.Session() as db:
            (stored,) = db.scalars(select(AccessToken.token_hash)).all()
        self.assertNotEqual(stored, first["access_token"])

    def test_wrong_claim_secret_is_404(self) -> None:
        created = self.request_access()
        response = self.client.get(f"/access-requests/{created['request_id']}/status", headers={"X-Claim-Secret": "x" * 20})
        self.assertEqual(response.status_code, 404)

    def test_rejected_request_issues_no_token(self) -> None:
        created = self.request_access()
        self.assertEqual(self.approve(created["request_id"], approve=False).json()["status"], "rejected")
        self.assertNotIn("access_token", self.poll(created).json())
        self.assertEqual(self.approve(created["request_id"]).status_code, 409)  # already decided

    def test_summary_is_totals_only_for_the_approved_scopes(self) -> None:
        _, token = self.approved_token()
        body = self.summary(token).json()
        self.assertEqual((body["sales_total_ngn"], body["total_owed_ngn"], body["active_days"]), (110000, 30000, 1))
        self.assertEqual(set(body), {"period_days", "generated_at", "scopes", "sales_total_ngn", "active_days", "total_owed_ngn"})

        _, narrow = self.approved_token(data_scopes=["total_owed"])
        self.assertEqual(set(self.summary(narrow).json()), {"period_days", "generated_at", "scopes", "total_owed_ngn"})

    def test_no_customer_name_or_profile_data_ever_appears_in_the_summary(self) -> None:
        _, token = self.approved_token()
        text = self.summary(token).text
        for private in ("Mama Ngozi", "Ngozi", PHONE, "Mile 12", "Ada", "rice", "beans", "carry", '"id"'):
            with self.subTest(private=private):
                self.assertNotIn(private, text)

    def test_status_codes_and_log_rows_for_each_token_state(self) -> None:
        request_id, token = self.approved_token()
        self.assertEqual(self.summary(token).status_code, 200)
        self.assertEqual(self.summary(None).json()["error"]["code"], "missing_token")
        self.assertEqual(self.summary("not-a-token").json()["error"]["code"], "invalid_token")

        with self.Session() as db:
            db.execute(update(AccessToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
            db.commit()
        expired = self.summary(token)
        self.assertEqual((expired.status_code, expired.json()["error"]["code"]), (401, "expired"))

        self.client.delete(f"/access/{request_id}", headers=self.headers)
        revoked = self.summary(token)
        self.assertEqual((revoked.status_code, revoked.json()["error"]["code"]), (403, "revoked"))

        results = self.log_results()
        for result in ("ok", "missing_token", "invalid_token", "expired", "revoked"):
            self.assertIn(result, results)

    def test_revoke_takes_effect_immediately(self) -> None:
        request_id, token = self.approved_token()
        self.assertEqual(self.summary(token).status_code, 200)
        body = self.client.delete(f"/access/{request_id}", headers=self.headers).json()
        self.assertEqual(body["status"], "revoked")
        self.assertEqual(self.summary(token).status_code, 403)

    def test_another_trader_cannot_see_or_decide_the_request(self) -> None:
        created = self.request_access()
        _, other = self.onboard(phone="08030000009")
        self.assertEqual(self.client.get("/access-requests", headers=other).json(), [])
        response = self.client.post(f"/access-requests/{created['request_id']}/approve", headers=other, json={"approve": True})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.delete(f"/access/{created['request_id']}", headers=other).status_code, 404)

    def test_every_decision_is_logged(self) -> None:
        request_id, _ = self.approved_token()
        (request,) = self.client.get("/access-requests", headers=self.headers).json()
        self.assertEqual([row["result"] for row in reversed(request["log"])], ["requested", "approved", "token_issued"])
        with self.Session() as db:
            self.assertEqual(db.scalar(select(func.count(AccessLog.id)).where(AccessLog.request_id == request_id)), 3)
