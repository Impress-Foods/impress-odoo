from .test_common import CampaignCase


class TestStockMove(CampaignCase):
    def test_demand_deletion(self) -> None:
        QTY = 120.0
        HALF_QTY = QTY / 2
        move = self.env["stock.move"].create(
            {
                "name": "move",
                "product_id": self.end_prod_a_red.id,
                "product_uom_qty": QTY,
                "state": "waiting",
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )

        self.assertEqual(move.campaign_qty_to_supply, QTY)
        self.assertTrue(move.campaign_can_be_added)

        demand = self.env["mrp.campaign.demand"].create(
            {"product_id": self.end_prod_a_red.id}
        )

        proxy_1 = self.env["mrp.campaign.demand.proxy"].create(
            {"demand_id": demand.id, "move_id": move.id, "promised_qty": HALF_QTY}
        )

        self.env["mrp.campaign.demand.proxy"].create(
            {"demand_id": demand.id, "move_id": move.id, "promised_qty": HALF_QTY}
        )

        self.assertEqual(move.campaign_qty_to_supply, 0)
        self.assertFalse(move.campaign_can_be_added)

        proxy_1.unlink()

        self.assertEqual(move.campaign_qty_to_supply, HALF_QTY)
        self.assertTrue(move.campaign_can_be_added)

        demand.unlink()

        self.assertEqual(move.campaign_qty_to_supply, QTY)
        self.assertTrue(move.campaign_can_be_added)

    def test_campaign_deletion(self) -> None:
        QTY = 100.0
        move = self.env["stock.move"].create(
            {
                "name": "move",
                "product_id": self.end_prod_a_red.id,
                "product_uom_qty": QTY,
                "state": "waiting",
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )

        self.assertEqual(move.campaign_qty_to_supply, QTY)
        self.assertTrue(move.campaign_can_be_added)

        campaign = self.create_campaign(self.bulk_material)

        demand = self.env["mrp.campaign.demand"].create(
            {"product_id": self.end_prod_a_red.id, "campaign_id": campaign.id}
        )

        self.env["mrp.campaign.demand.proxy"].create(
            {"demand_id": demand.id, "move_id": move.id, "promised_qty": QTY}
        )

        self.assertEqual(move.campaign_qty_to_supply, 0)
        self.assertFalse(move.campaign_can_be_added)

        campaign.unlink()

        self.assertEqual(move.campaign_qty_to_supply, QTY)
        self.assertTrue(move.campaign_can_be_added)

    def test_sale_customer_ref(self) -> None:
        """Test that sale_customer_ref correctly extracts
        client_order_ref from sale order."""
        move = self.env["stock.move"].create(
            {
                "name": "move",
                "product_id": self.end_prod_a_red.id,
                "product_uom_qty": 10.0,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
            }
        )

        self.assertEqual(move.sale_customer_ref, "")

        if "sale_line_id" in self.env["stock.move"]:
            partner = self.env["res.partner"].create({"name": "Test Customer"})
            sale_order = self.env["sale.order"].create(
                {
                    "partner_id": partner.id,
                    "client_order_ref": "PO-12345",
                }
            )
            sale_line = self.env["sale.order.line"].create(
                {
                    "order_id": sale_order.id,
                    "product_id": self.end_prod_a_red.id,
                    "product_uom_qty": 10.0,
                }
            )
            move.sale_line_id = sale_line

            self.assertEqual(move.sale_customer_ref, "PO-12345")
