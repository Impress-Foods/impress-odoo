from .test_common import CampaignCase


class TestStockMove(CampaignCase):
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

        self.assertEqual(move.sale_customer_ref, False)

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

    def test_get_qty_to_fulfill_single(self) -> None:
        QTY = 100.0
        move = self.env["stock.move"].create(
            {
                "name": f"test move for {self.bulk_material.display_name}",
                "product_id": self.bulk_material.id,
                "product_uom_qty": QTY,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )

        campaign = self.create_campaign(self.bulk_material)

        demand = self.env["mrp.campaign.demand"].create(
            {"product_id": self.bulk_material.id, "campaign_id": campaign.id}
        )

        self.assertEqual(move._get_qty_to_fulfill(), QTY)

        target = self.env["mrp.campaign.demand.target"].create(
            {"demand_id": demand.id, "promised_qty": QTY, "target_id": move.id}
        )
        self.assertEqual(target.workflow_type, "direct")
        self.assertEqual(target.target_model, "stock.move")

        self.assertEqual(move._get_qty_to_fulfill(), 0)

    def test_get_qty_to_fulfill_batch(self) -> None:
        QTY = 100.0
        move_a = self.env["stock.move"].create(
            {
                "name": f"test move A for {self.bulk_material.display_name}",
                "product_id": self.bulk_material.id,
                "product_uom_qty": QTY,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )
        move_b = self.env["stock.move"].create(
            {
                "name": f"test move B for {self.bulk_material.display_name}",
                "product_id": self.bulk_material.id,
                "product_uom_qty": QTY,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )

        campaign = self.create_campaign(self.bulk_material)
        demand = self.env["mrp.campaign.demand"].create(
            {"product_id": self.bulk_material.id, "campaign_id": campaign.id}
        )

        # move_a gets partial promise, move_b gets full promise
        self.env["mrp.campaign.demand.target"].create(
            {"demand_id": demand.id, "promised_qty": QTY / 2, "target_id": move_a.id}
        )
        self.env["mrp.campaign.demand.target"].create(
            {"demand_id": demand.id, "promised_qty": QTY, "target_id": move_b.id}
        )

        both_moves = move_a | move_b
        result = self.env["stock.move"]._get_qty_to_fulfill_by_moves(both_moves)

        self.assertEqual(result[move_a.id], QTY / 2)
        self.assertEqual(result[move_b.id], 0)

        # Empty recordset returns empty dict
        self.assertEqual(
            self.env["stock.move"]._get_qty_to_fulfill_by_moves(self.env["stock.move"]),
            {},
        )
        QTY = 100.0
        move = self.env["stock.move"].create(
            {
                "name": f"test move for {self.bulk_material.display_name}",
                "product_id": self.bulk_material.id,
                "product_uom_qty": QTY,
                "location_id": self.stock_location.id,
                "location_dest_id": self.stock_location.id,
                "state": "waiting",
            }
        )

        self.assertEqual(move._get_qty_to_fulfill(), QTY)

        campaign_1 = self.create_campaign(self.bulk_material)

        demand_1 = self.env["mrp.campaign.demand"].create(
            {"product_id": self.bulk_material.id, "campaign_id": campaign_1.id}
        )

        self.env["mrp.campaign.demand.target"].create(
            {"demand_id": demand_1.id, "promised_qty": QTY / 2, "target_id": move.id}
        )

        self.assertEqual(move._get_qty_to_fulfill(), QTY / 2)

        campaign_2 = self.create_campaign(self.bulk_material)

        demand_2 = self.env["mrp.campaign.demand"].create(
            {"product_id": self.bulk_material.id, "campaign_id": campaign_2.id}
        )
        self.env["mrp.campaign.demand.target"].create(
            {"demand_id": demand_2.id, "promised_qty": QTY / 2, "target_id": move.id}
        )

        self.assertEqual(move._get_qty_to_fulfill(), 0)
