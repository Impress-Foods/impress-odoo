import logging

from odoo.tests import Form, TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("standard", "impress")
class TestSaleOrder(TransactionCase):
    def setUp(self):
        super().setUp()
        ref = self.env.ref
        self.sale_order_model = self.env["sale.order"]
        self.sale_order_line_model = self.env["sale.order.line"]

        self.partner = self.env["res.partner"].create({"name": "Test"})

        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "product",
            }
        )

        self.wh = ref("stock.warehouse0")
        self.wh.delivery_steps = "pick_ship"

    def test_create_2_pickings(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()

        self.assertEqual(len(order.picking_ids), 2)
        self.assertEqual(
            len(
                order.picking_ids.filtered_domain(
                    [("picking_type_id.code", "=", "internal")]
                )
            ),
            1,
        )

    def test_unreserved_prep(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()

        prep = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "internal")]
        )[0]

        self.assertEqual(len(prep), 1)

        prep.do_unreserve()

        self.assertEqual(order.delivery_status, "pending")

    def test_reserved_prep(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()

        order.picking_ids.filtered_domain([("picking_type_id.code", "=", "internal")])[
            0
        ]

        self.assertEqual(order.delivery_status, "prep_ready")

    def test_done_prep(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()

        prep = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "internal")]
        )[0]

        prep.button_validate()
        self.assertEqual(order.delivery_status, "ready")

    def test_fully_delivered(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()

        prep = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "internal")]
        )[0]

        out = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "outgoing")]
        )[0]

        prep.button_validate()
        out.button_validate()
        self.assertEqual(order.delivery_status, "full")

    def test_prep_backorder(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 5,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()
        prep = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "internal")]
        )[0]

        backorder_wizard_dict = prep.button_validate()
        backorder_wizard_form = Form(
            self.env[backorder_wizard_dict["res_model"]].with_context(  # type: ignore
                backorder_wizard_dict["context"]  # type: ignore
            )
        )
        backorder_wizard_form.save().process()  # type: ignore

        self.assertEqual(order.delivery_status, "in_prep")

    def test_prep_backorder_done(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 5,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()
        prep = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "internal")]
        )[0]

        backorder_wizard_dict = prep.button_validate()
        backorder_wizard_form = Form(
            self.env[backorder_wizard_dict["res_model"]].with_context(  # type: ignore
                backorder_wizard_dict["context"]  # type: ignore
            )
        )
        backorder_wizard_form.save().process()  # type: ignore

        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 5,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )

        bo = prep.backorder_ids[0]
        bo.action_assign()
        bo.button_validate()

        self.assertEqual(order.delivery_status, "ready")

    def test_delivery_backorder(self):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "quantity": 10,
                "location_id": self.env.ref("stock.stock_location_stock").id,  # type: ignore
            }
        )
        order = self.sale_order_model.create({"partner_id": self.partner.id})
        self.sale_order_line_model.create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 10}
        )
        order.action_confirm()

        prep = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "internal")]
        )[0]

        delivery = order.picking_ids.filtered_domain(
            [("picking_type_id.code", "=", "outgoing")]
        )[0]

        prep.button_validate()

        # Set a qty less than the demand on the delivery to force a BO
        delivery.move_line_ids[0].quantity = 5

        backorder_wizard_dict = delivery.button_validate()
        backorder_wizard_form = Form(
            self.env[backorder_wizard_dict["res_model"]].with_context(  # type: ignore
                backorder_wizard_dict["context"]  # type: ignore
            )
        )
        backorder_wizard_form.save().process()  # type: ignore

        message = ""
        for picking in order.picking_ids:
            message += "\n"
            message += f"{picking.id}: {picking.picking_type_code} - {picking.state}"

        self.assertEqual(order.delivery_status, "partial", message)
