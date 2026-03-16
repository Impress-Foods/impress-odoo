from odoo.addons.mrp_campaign.tests.test_common import CampaignCase


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
