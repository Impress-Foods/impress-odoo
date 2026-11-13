"""The price in the 850 is contractual: a quantity change must not replace it."""

from .common import CostcoShipmentCase


class TestPriceProtection(CostcoShipmentCase):
    def _costco_line(self, order):
        return order.order_line.filtered("costco_sku")

    def _make_pricelist_differ(self, line):
        """List the product at a price other than the one on the order."""
        line.product_id.list_price = line.price_unit + 100
        self.assertNotEqual(line.product_id.lst_price, line.price_unit)

    def test_a_partial_cancellation_keeps_the_price_of_the_850(self):
        order, __ = self._order(kits=5)
        line = self._costco_line(order)
        price = line.price_unit
        self._make_pricelist_differ(line)
        cancellation = self.env["edi.rithum.costco.cancellation"].create(
            {
                "order_id": order.id,
                "reason_id": self.env.ref(
                    "edi_rithum_costco.cancel_reason_out_of_stock"
                ).id,
                "line_ids": order.action_costco_cancel()["context"]["default_line_ids"],
            }
        )
        cancellation.line_ids.quantity = 2
        cancellation.action_confirm()
        self.assertEqual(line.product_uom_qty, 3)
        self.assertEqual(line.price_unit, price)

    def test_a_manual_quantity_edit_keeps_the_price_of_the_850(self):
        order, __ = self._order(kits=5)
        line = self._costco_line(order)
        price = line.price_unit
        self._make_pricelist_differ(line)
        line.product_uom_qty = 4
        self.assertEqual(line.price_unit, price)

    def test_a_line_without_a_costco_sku_still_follows_the_pricelist(self):
        order, __ = self._order(kits=5)
        other = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.components["COMP-A"].id,
                "product_uom_qty": 1,
            }
        )
        other.product_id.list_price = 7
        other.product_uom_qty = 2
        self.assertEqual(other.price_unit, 7)
