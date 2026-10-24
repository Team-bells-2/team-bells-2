"""Inventory writes (FR-S23, FR-S24; BR-I1 to I3). Run: cd server && python -m unittest discover -s tests -t ."""

from tests.support import ApiTestCase


class InventoryWriteTest(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trader_id, self.headers = self.onboard()

    def create(self, **fields: object) -> dict:
        response = self.client.post("/inventory", headers=self.headers, json={"name": "Rice", "unit": "bag", **fields})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def stock(self, item_id: int, change: float, reason: str):
        return self.client.post(
            f"/inventory/{item_id}/stock", headers=self.headers, json={"quantity_change": change, "reason": reason}
        )

    def test_added_item_appears_in_list(self) -> None:
        item = self.create(unit_cost_ngn=58000, reorder_level=3, reorder_quantity=10)
        self.assertEqual((item["quantity_on_hand"], item["low_stock"]), (0, True))
        listed = self.client.get("/inventory", headers=self.headers).json()
        self.assertEqual([(i["id"], i["name"], i["reorder_quantity"]) for i in listed], [(item["id"], "Rice", 10)])

    def test_quantity_is_derived_from_movements(self) -> None:
        item_id = self.create()["id"]
        self.assertEqual(self.stock(item_id, 10, "opening").json()["quantity_on_hand"], 10)
        self.assertEqual(self.stock(item_id, 5, "restock").json()["quantity_on_hand"], 15)
        self.assertEqual(self.stock(item_id, -2, "adjustment").json()["quantity_on_hand"], 13)

    def test_editing_details_never_changes_quantity(self) -> None:
        item_id = self.create()["id"]
        self.stock(item_id, 10, "opening")
        body = self.client.patch(
            f"/inventory/{item_id}", headers=self.headers, json={"unit_cost_ngn": 60000, "reorder_level": 4}
        ).json()
        self.assertEqual((body["unit_cost_ngn"], body["reorder_level"], body["quantity_on_hand"]), (60000, 4, 10))
        response = self.client.patch(f"/inventory/{item_id}", headers=self.headers, json={"quantity_on_hand": 99})
        self.assertEqual(response.status_code, 422)

    def test_duplicate_name_ignoring_case_is_409(self) -> None:
        self.create()
        response = self.client.post("/inventory", headers=self.headers, json={"name": "rice", "unit": "bag"})
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (409, "item_exists"))

    def test_rename_to_an_existing_name_is_409(self) -> None:
        self.create()
        beans_id = self.create(name="Beans")["id"]
        response = self.client.patch(f"/inventory/{beans_id}", headers=self.headers, json={"name": "RICE"})
        self.assertEqual(response.status_code, 409)

    def test_movement_rules(self) -> None:
        item_id = self.create()["id"]
        self.stock(item_id, 3, "opening")
        cases = [
            (-1, "restock", 422, "invalid_movement"),
            (-1, "opening", 422, "invalid_movement"),
            (0, "adjustment", 422, "invalid_movement"),
            (-5, "adjustment", 409, "negative_stock"),
        ]
        for change, reason, status, code in cases:
            with self.subTest(change=change, reason=reason):
                response = self.stock(item_id, change, reason)
                self.assertEqual((response.status_code, response.json()["error"]["code"]), (status, code))
        self.assertEqual(self.stock(item_id, 1, "sale").status_code, 422)  # sales come from the ledger only

    def test_another_traders_item_is_404(self) -> None:
        item_id = self.create()["id"]
        _, other = self.onboard(phone="08030000009")
        self.assertEqual(self.client.patch(f"/inventory/{item_id}", headers=other, json={"unit": "kg"}).status_code, 404)
        response = self.client.post(
            f"/inventory/{item_id}/stock", headers=other, json={"quantity_change": 1, "reason": "restock"}
        )
        self.assertEqual(response.status_code, 404)
