"""The stock of the products bound to Costco goes out as an inventory advice."""

from datetime import date
from unittest import mock

from .common import CostcoShipmentCase

EXCHANGE_SEND = "exchange_send"


class TestInventoryFlow(CostcoShipmentCase):
    def _bind(self, **changes):
        binding = self.env["edi.rithum.costco.product"].create(
            {
                "backend_id": self.backend.id,
                "product_id": self.kit.id,
                "costco_sku": "COSTCO-1",
                **changes,
            }
        )
        return binding

    def _send(self):
        errors = []
        with mock.patch.object(self.env.registry["edi.backend"], EXCHANGE_SEND) as send:
            record = self.backend.costco_send_inventory(errors.append)
        return record, errors, send

    def _stocked(self):
        """A received order (so Costco's interchange ID is known) and a binding."""
        order, picking = self._order(kits=3)
        return order, picking, self._bind()

    def test_the_stock_of_a_kit_is_the_whole_kits_its_components_allow(self):
        self._stocked()
        record, errors, send = self._send()
        self.assertFalse(errors)
        send.assert_called_once()
        text = self._text(record)
        # 100 of COMP-A at 2 per kit, 100 of COMP-B at 1: 50 kits, minus the 3
        # reserved for the order (6 of A, 3 of B): 94 / 2 = 47 and 97, so 47.
        self.assertIn("LIN**VN*KIT-1*SK*COSTCO-1~", text)
        self.assertIn("QTY*61*47*EA~", text)
        self.assertIn("REF*WS*2001*47~", text)
        self.assertEqual(record.x12_control_number, str(int(text.split("*")[13])))

    def test_a_warehouse_without_a_rithum_id_is_not_reported(self):
        self._stocked()
        other = self.env["stock.warehouse"].create({"name": "Elsewhere", "code": "ELS"})
        record, errors, __ = self._send()
        self.assertFalse(errors)
        self.assertEqual(self._text(record).count("REF*WS*"), 1)
        self.assertFalse(other.costco_warehouse_code)

    def test_a_second_warehouse_is_reported_with_its_own_stock(self):
        self._stocked()
        other = self.env["stock.warehouse"].create(
            {"name": "East", "code": "EST", "costco_warehouse_code": "2002"}
        )
        for component in self.components.values():
            self.env["stock.quant"]._update_available_quantity(
                component, other.lot_stock_id, 10
            )
        record, errors, __ = self._send()
        self.assertFalse(errors)
        text = self._text(record)
        self.assertIn("REF*WS*2002*5~", text)
        self.assertIn("QTY*61*52*EA~", text)

    def test_a_deactivated_binding_is_not_reported(self):
        __, __, binding = self._stocked()
        binding.active = False
        record, errors, send = self._send()
        send.assert_not_called()
        self.assertTrue(errors)
        self.assertIn("No product is bound", errors[0])
        self.assertTrue(record.exchange_error)

    def test_a_discontinued_date_is_reported(self):
        __, __, binding = self._stocked()
        binding.discontinued_on = date(2026, 12, 31)
        record, errors, __ = self._send()
        self.assertFalse(errors)
        self.assertIn("DTM*036*20261231~", self._text(record))

    def test_nothing_is_sent_before_costcos_interchange_id_is_known(self):
        self._stocked()
        self.env.ref("edi_rithum_costco.rithum_partner_costco").x12_id = False
        record, errors, send = self._send()
        send.assert_not_called()
        self.assertIn("interchange ID of the Rithum partner", errors[0])
        self.assertTrue(record.exchange_error)

    def test_the_inventory_goes_out_as_the_id_set_for_costco(self):
        self._stocked()
        self.env.ref("edi_rithum_costco.rithum_partner_costco").write(
            {"own_qualifier": "01", "own_id": "OURS-COSTCO"}
        )
        record, errors, __ = self._send()
        self.assertFalse(errors)
        isa = self._text(record).split("~")[0].split("*")
        self.assertEqual((isa[5], isa[6].strip()), ("01", "OURS-COSTCO"))

    def test_a_product_without_a_free_quantity_is_reported_as_zero(self):
        self._stocked()
        quants = self.env["stock.quant"].search(
            [("product_id", "in", [c.id for c in self.components.values()])]
        )
        quants.inventory_quantity = 0
        quants.action_apply_inventory()
        record, errors, __ = self._send()
        self.assertFalse(errors)
        text = self._text(record)
        self.assertIn("QTY*61*0*EA~", text)
        self.assertIn("REF*WS*2001*0~", text)

    def test_products_are_bound_from_the_costco_orders_received(self):
        self._order(kits=3)
        self.assertFalse(self.env["edi.rithum.costco.product"].search([]))
        self.backend.action_costco_bind_products()
        binding = self.env["edi.rithum.costco.product"].search([])
        self.assertEqual(binding.product_id, self.kit)
        self.assertEqual(binding.costco_sku, "COSTCO-1")
        self.backend.action_costco_bind_products()
        self.assertEqual(len(self.env["edi.rithum.costco.product"].search([])), 1)

    def test_a_new_costco_sku_on_an_order_updates_the_binding(self):
        order, __ = self._order(kits=3)
        binding = self._bind(costco_sku="OLD")
        self.env["edi.rithum.costco.product"].bind_order_lines(
            self.backend, order.order_line
        )
        self.assertEqual(binding.costco_sku, "COSTCO-1")

    def test_receiving_an_order_binds_its_products(self):
        order, __ = self._order(kits=3)
        self.env["edi.rithum.costco.product"].bind_order_lines(
            self.backend, order.order_line
        )
        self.assertEqual(
            self.env["edi.rithum.costco.product"].search([]).product_id, self.kit
        )

    def test_the_scheduled_action_sends_the_inventory(self):
        self._stocked()
        with mock.patch.object(self.env.registry["edi.backend"], EXCHANGE_SEND) as send:
            self.env["edi.backend"]._cron_costco_send_inventory()
        send.assert_called_once()
        cron = self.env.ref("edi_rithum_costco.ir_cron_costco_inventory")
        self.assertFalse(cron.active)

    def test_the_buttons_are_on_the_backend_form(self):
        arch = self.env["edi.backend"].get_view(view_type="form")["arch"]
        self.assertIn('name="action_costco_send_inventory"', arch)
        self.assertIn('name="action_costco_bind_products"', arch)

    def test_the_button_reports_the_outcome(self):
        self._stocked()
        with mock.patch.object(self.env.registry["edi.backend"], EXCHANGE_SEND):
            action = self.backend.action_costco_send_inventory()
        self.assertEqual(action["params"]["type"], "success")
        self.backend.x12_sender_id = False
        action = self.backend.action_costco_send_inventory()
        self.assertEqual(action["params"]["type"], "danger")
        self.assertIn("sender ID", action["params"]["message"])

    def test_the_backend_counts_its_bindings_and_opens_them(self):
        self.assertEqual(self.backend.costco_product_count, 0)
        binding = self._bind()
        binding.active = False
        self.backend.invalidate_recordset()
        self.assertEqual(self.backend.costco_product_count, 1)
        action = self.backend.action_view_costco_products()
        self.assertEqual(action["res_model"], "edi.rithum.costco.product")
        found = (
            self.env[action["res_model"]]
            .with_context(**action["context"])
            .search(action["domain"])
        )
        self.assertEqual(found, binding)
        self.assertEqual(action["context"]["default_backend_id"], self.backend.id)

    def test_the_smart_button_is_on_the_backend_form(self):
        arch = self.env["edi.backend"].get_view(view_type="form")["arch"]
        self.assertIn('name="action_view_costco_products"', arch)

    def test_the_inactive_and_discontinued_filters_find_their_bindings(self):
        arch = self.env["edi.rithum.costco.product"].get_view(view_type="search")[
            "arch"
        ]
        self.assertIn('name="inactive"', arch)
        self.assertIn('name="discontinued"', arch)
        binding = self._bind(discontinued_on=date(2026, 12, 31))
        model = self.env["edi.rithum.costco.product"]
        self.assertEqual(model.search([("active", "=", False)]), model.browse())
        binding.active = False
        self.assertEqual(model.search([("active", "=", False)]), binding)
        self.assertEqual(model.search([("discontinued_on", "!=", False)]), model)
        self.assertEqual(
            model.with_context(active_test=False).search(
                [("discontinued_on", "!=", False)]
            ),
            binding,
        )
