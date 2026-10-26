# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.tests.common import TransactionCase

from odoo.addons.purchase.models.purchase_order import PurchaseOrder
from odoo.addons.quality.models.quality import QualityAlert
from odoo.addons.sale.models.sale_order import SaleOrder


class TestQualityAlert(TransactionCase):
    """The alert's origin, its new descriptive fields, and the order links."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("quality.group_quality_user")
        cls.team = cls.env["quality.alert.team"].create(
            {"name": "Quality Alert Test Team", "company_id": cls.env.company.id}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Quality Alert Product",
                "is_storable": True,
                "tracking": "lot",
            }
        )
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Quality Alert Supplier", "supplier_rank": 1}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Quality Alert Customer", "customer_rank": 1}
        )
        cls.purchase_order = cls._create_purchase_order(cls.supplier)
        cls.sale_order = cls._create_sale_order(cls.customer)

    @classmethod
    def _create_purchase_order(cls, partner) -> PurchaseOrder:
        order = cls.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_qty": 5.0,
                            "price_unit": 1.0,
                            "product_uom_id": cls.product.uom_id.id,
                        }
                    )
                ],
            }
        )
        order.button_confirm()
        return order

    @classmethod
    def _create_sale_order(cls, partner) -> SaleOrder:
        order = cls.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 5.0,
                            "product_uom_id": cls.product.uom_id.id,
                        }
                    )
                ],
            }
        )
        order.action_confirm()
        return order

    def _create_alert(self, **values) -> QualityAlert:
        return self.env["quality.alert"].create({"team_id": self.team.id, **values})

    def test_alert_type_defaults_to_complaint(self) -> None:
        alert = self._create_alert(product_id=self.product.id)
        self.assertEqual(alert.alert_type, "complaint")

        salubrity = self._create_alert(
            product_id=self.product.id, alert_type="salubrity"
        )
        self.assertEqual(salubrity.alert_type, "salubrity")

    def test_quantity_and_product_impact(self) -> None:
        alert = self._create_alert(
            product_id=self.product.id,
            quantity=2.5,
            impact_on_product=True,
        )
        self.assertEqual(alert.quantity, 2.5)
        self.assertTrue(alert.impact_on_product)

    def test_product_uom_defaults_from_product(self) -> None:
        alert = self._create_alert(product_id=self.product.id)
        self.assertEqual(alert.product_uom_id, self.product.uom_id)

    def test_product_uom_can_be_overridden(self) -> None:
        dozen = self.env.ref("uom.product_uom_dozen")
        alert = self._create_alert(
            product_id=self.product.id,
            product_uom_id=dozen.id,
        )
        self.assertEqual(alert.product_uom_id, dozen)

    def test_vendor_and_customer_follow_orders(self) -> None:
        alert = self._create_alert(
            purchase_order_id=self.purchase_order.id,
            sale_order_id=self.sale_order.id,
        )
        self.assertEqual(alert.vendor_id, self.supplier)
        self.assertEqual(alert.customer_id, self.customer)

        purchase_action = alert.action_view_purchase_order()
        self.assertEqual(purchase_action["res_model"], "purchase.order")
        self.assertEqual(purchase_action["res_id"], self.purchase_order.id)

        sale_action = alert.action_view_sale_order()
        self.assertEqual(sale_action["res_model"], "sale.order")
        self.assertEqual(sale_action["res_id"], self.sale_order.id)

    def test_purchase_order_is_detected_from_receipt(self) -> None:
        receipt = self.purchase_order.picking_ids
        self.assertTrue(receipt, "The purchase order should have a receipt")

        alert = self._create_alert(picking_id=receipt.id)

        self.assertEqual(alert.purchase_order_id, self.purchase_order)
        self.assertEqual(alert.vendor_id, self.supplier)
        self.assertFalse(alert.sale_order_id)

    def test_product_is_detected_from_purchase_order(self) -> None:
        alert = self._create_alert(purchase_order_id=self.purchase_order.id)

        self.assertEqual(alert.product_id, self.product)
        self.assertEqual(alert.product_tmpl_id, self.product.product_tmpl_id)

    def test_product_and_lot_are_detected_from_receipt(self) -> None:
        receipt = self.purchase_order.picking_ids
        lot = self.env["stock.lot"].create(
            {"name": "ALERT-RECEIPT-LOT", "product_id": self.product.id}
        )
        self.env["stock.move.line"].create(
            {
                "move_id": receipt.move_ids.id,
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "quantity": 1.0,
                "lot_id": lot.id,
                "location_id": receipt.location_id.id,
                "location_dest_id": receipt.location_dest_id.id,
            }
        )

        alert = self._create_alert(picking_id=receipt.id)

        self.assertEqual(alert.product_id, self.product)
        self.assertEqual(alert.lot_ids, lot)

        alert_onchange = self.env["quality.alert"].new(
            {"team_id": self.team.id, "picking_id": receipt.id}
        )
        alert_onchange._onchange_origin_product()
        self.assertEqual(alert_onchange.product_id, self.product)
        self.assertEqual(alert_onchange.lot_ids._origin, lot)

    def test_product_is_detected_from_sale_order(self) -> None:
        alert = self._create_alert(sale_order_id=self.sale_order.id)

        self.assertEqual(alert.product_id, self.product)
        self.assertEqual(alert.product_tmpl_id, self.product.product_tmpl_id)

    def test_manual_product_is_not_overridden(self) -> None:
        receipt = self.purchase_order.picking_ids
        other_product = self.env["product.product"].create(
            {"name": "Other Alert Product", "is_storable": True}
        )

        alert = self._create_alert(
            picking_id=receipt.id,
            product_id=other_product.id,
        )

        self.assertEqual(alert.product_id, other_product)
        self.assertEqual(alert.product_tmpl_id, other_product.product_tmpl_id)

    def test_sale_order_is_detected_from_delivery(self) -> None:
        delivery = self.sale_order.picking_ids
        self.assertTrue(delivery, "The sale order should have a delivery")

        alert = self._create_alert(picking_id=delivery.id)

        self.assertEqual(alert.sale_order_id, self.sale_order)
        self.assertEqual(alert.customer_id, self.customer)
        self.assertFalse(alert.purchase_order_id)

    def test_manual_order_overrides_detection(self) -> None:
        receipt = self.purchase_order.picking_ids
        other_order = self._create_purchase_order(self.supplier)

        alert = self._create_alert(
            picking_id=receipt.id,
            purchase_order_id=other_order.id,
        )

        self.assertEqual(alert.purchase_order_id, other_order)
        self.assertEqual(alert.vendor_id, self.supplier)

    def test_check_alert_keeps_its_transfer_and_orders(self) -> None:
        receipt = self.purchase_order.picking_ids
        lot = self.env["stock.lot"].create(
            {"name": "ALERT-CHECK-LOT", "product_id": self.product.id}
        )
        check = self.env["quality.check"].create(
            {
                "picking_id": receipt.id,
                "product_id": self.product.id,
                "team_id": self.team.id,
                "quality_state": "fail",
                "lot_ids": [Command.set(lot.ids)],
            }
        )

        action = check.do_alert()
        alert = self.env["quality.alert"].browse(action["res_id"])

        self.assertEqual(alert.check_id, check)
        self.assertEqual(alert.picking_id, receipt)
        self.assertEqual(alert.purchase_order_id, self.purchase_order)
        self.assertEqual(alert.vendor_id, self.supplier)
        self.assertEqual(alert.product_id, self.product)
        self.assertEqual(alert.lot_ids, lot)

    def test_order_alert_count_and_action(self) -> None:
        alert = self._create_alert(purchase_order_id=self.purchase_order.id)
        self.assertEqual(self.purchase_order.quality_alert_count, 1)

        action = self.purchase_order.action_view_quality_alerts()
        self.assertEqual(action["res_id"], alert.id)
        self.assertEqual(action["res_model"], "quality.alert")
        self.assertEqual(action["context"]["default_product_id"], self.product.id)

        second_alert = self._create_alert(purchase_order_id=self.purchase_order.id)
        self.assertEqual(self.purchase_order.quality_alert_count, 2)

        action = self.purchase_order.action_view_quality_alerts()
        self.assertEqual(
            action["domain"], [("purchase_order_id", "=", self.purchase_order.id)]
        )
        self.assertIn(second_alert, self.purchase_order.quality_alert_ids)

    def test_sale_order_alert_count_and_action(self) -> None:
        alert = self._create_alert(sale_order_id=self.sale_order.id)
        self.assertEqual(self.sale_order.quality_alert_count, 1)

        action = self.sale_order.action_view_quality_alerts()
        self.assertEqual(action["res_id"], alert.id)
        self.assertEqual(action["res_model"], "quality.alert")
        self.assertEqual(action["context"]["default_product_id"], self.product.id)

    def test_alert_without_origin(self) -> None:
        alert = self._create_alert()
        self.assertFalse(alert.product_id)
        self.assertFalse(alert.product_tmpl_id)
        self.assertFalse(alert.lot_ids)
        self.assertFalse(alert.purchase_order_id)
        self.assertFalse(alert.sale_order_id)
        self.assertFalse(alert.vendor_id)
        self.assertFalse(alert.customer_id)
        self.assertFalse(alert.product_uom_id)
