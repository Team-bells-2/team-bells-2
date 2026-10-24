"""Onboarding and profile (FR-S21, FR-S22, error shape). Run: cd server && python -m unittest discover -s tests -t ."""

from tests.support import ApiTestCase

ONBOARDING = {
    "name": "Ada Obi",
    "phone": "08031234567",
    "business_name": "Ada Foods",
    "sector": "foodstuff",
    "location_name": "Mile 12",
}


class OnboardingTest(ApiTestCase):
    def test_onboarding_returns_token_and_trader_with_location_coordinates(self) -> None:
        response = self.client.post("/onboarding", json={**ONBOARDING, "location_name": "mile 12"})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["token"])
        self.assertEqual(body["trader"]["location_name"], "Mile 12")
        self.assertEqual((body["trader"]["latitude"], body["trader"]["longitude"]), (6.605, 3.398))

    def test_duplicate_phone_is_409(self) -> None:
        self.client.post("/onboarding", json=ONBOARDING)
        response = self.client.post("/onboarding", json=ONBOARDING)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "phone_taken")

    def test_unknown_location_is_422(self) -> None:
        response = self.client.post("/onboarding", json={**ONBOARDING, "location_name": "Mars"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "unknown_location")

    def test_main_items_become_inventory_with_opening_stock(self) -> None:
        items = [
            {"name": "Rice", "unit": "bag", "opening_quantity": 10, "reorder_level": 3, "reorder_quantity": 10},
            {"name": "Garri", "unit": "bag"},
        ]
        token = self.client.post("/onboarding", json={**ONBOARDING, "items": items}).json()["token"]
        inventory = self.client.get("/inventory", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(
            [(i["name"], i["quantity_on_hand"], i["reorder_quantity"]) for i in inventory],
            [("Garri", 0, 0), ("Rice", 10, 10)],
        )

    def test_duplicate_item_names_are_rejected_and_nothing_is_saved(self) -> None:
        items = [{"name": "Rice", "unit": "bag"}, {"name": "rice", "unit": "bag"}]
        response = self.client.post("/onboarding", json={**ONBOARDING, "items": items})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/onboarding", json=ONBOARDING).status_code, 201)  # phone still free

    def test_missing_required_field_uses_error_shape(self) -> None:
        response = self.client.post("/onboarding", json={"name": "Ada"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(), {"error": {"code": "validation_error", "message": "phone: Field required"}}
        )


class ProfileTest(ApiTestCase):
    def test_get_profile(self) -> None:
        _, headers = self.onboard()
        body = self.client.get("/profile", headers=headers).json()
        self.assertEqual((body["name"], body["business_name"]), ("Ada Obi", "Ada Foods"))

    def test_missing_and_invalid_tokens_are_401(self) -> None:
        self.assertEqual(self.client.get("/profile").json()["error"]["code"], "missing_token")
        response = self.client.get("/profile", headers={"Authorization": "Bearer nope"})
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (401, "invalid_token"))

    def test_patch_persists_and_takes_coordinates_from_location(self) -> None:
        _, headers = self.onboard()
        self.client.patch(
            "/profile", headers=headers, json={"business_name": "Ada Ventures", "location_name": "Oyingbo"}
        )
        body = self.client.get("/profile", headers=headers).json()
        self.assertEqual((body["business_name"], body["location_name"]), ("Ada Ventures", "Oyingbo"))
        self.assertEqual((body["latitude"], body["longitude"]), (6.488, 3.385))

    def test_phone_is_not_editable(self) -> None:
        _, headers = self.onboard()
        response = self.client.patch("/profile", headers=headers, json={"phone": "0800"})
        self.assertEqual(response.status_code, 422)

    def test_unknown_location_on_patch_is_422(self) -> None:
        _, headers = self.onboard()
        response = self.client.patch("/profile", headers=headers, json={"location_name": "Mars"})
        self.assertEqual(response.json()["error"]["code"], "unknown_location")

    def test_one_traders_token_never_returns_another_trader(self) -> None:
        _, headers_a = self.onboard(phone="08030000001")
        _, headers_b = self.onboard(phone="08030000002")
        self.assertEqual(self.client.get("/profile", headers=headers_a).json()["phone"], "08030000001")
        self.assertEqual(self.client.get("/profile", headers=headers_b).json()["phone"], "08030000002")
