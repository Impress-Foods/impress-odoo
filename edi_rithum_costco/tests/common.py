"""Shared fixtures: a Costco order, its delivery, packages and a validation."""

import base64
import itertools
from unittest import mock

from odoo.tests.common import TransactionCase

from .maps import MAP_PATH
from .test_flow_850 import SCHEME, SENDER, _order_text

OUR_ID = "OURID"
TRACKING = ("1Z999AA10123456784", "1Z999AA10123456792")
PER_KIT = {"COMP-A": 2, "COMP-B": 1}


class CostcoShipmentCase(TransactionCase):
    _orders = itertools.count(1)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env.ref("edi_rithum.rithum_backend")
        cls.backend.write({"x12_sender_id": OUR_ID})
        cls.env.ref("edi_rithum_costco.rithum_partner_costco").x12_id = SENDER
        scheme = cls.env.ref("edi_x12.id_category_x12")
        partner = cls.env["res.partner"].create({"name": "Retail Customer"})
        cls.env["res.partner.id_number"].create(
            {"partner_id": partner.id, "category_id": scheme.id, "name": SENDER}
        )
        cls.env.ref("uom.product_uom_unit").unece_code = "C62"
        cls.warehouse = cls.env["stock.warehouse"].search([], limit=1)
        cls.warehouse.costco_warehouse_code = "2001"
        cls.components = {code: cls._storable(code) for code in PER_KIT}
        cls.kit = cls.env["product.product"].create(
            {"name": "Gift box", "default_code": "KIT-1", "type": "consu"}
        )
        cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.kit.product_tmpl_id.id,
                "type": "phantom",
                "bom_line_ids": [
                    (0, 0, {"product_id": cls.components[code].id, "product_qty": qty})
                    for code, qty in PER_KIT.items()
                ],
            }
        )
        cls.service = cls.env["product.product"].create(
            {"name": "UPS service", "type": "service"}
        )
        cls.carrier = cls.env["delivery.carrier"].create(
            {
                "name": "UPS Ground",
                "delivery_type": "fixed",
                "product_id": cls.service.id,
                "costco_shipping_method": "UPSN_CG",
            }
        )

    @classmethod
    def _storable(cls, code):
        product = cls.env["product.product"].create(
            {"name": code, "default_code": code, "type": "consu", "is_storable": True}
        )
        stock = cls.env["stock.warehouse"].search([], limit=1).lot_stock_id
        cls.env["stock.quant"]._update_available_quantity(product, stock, 100)
        return product

    def _order(self, kits=3, from_edi=True, sku="KIT-1"):
        """A confirmed Costco order for ``kits`` boxes, and its delivery."""
        text = _order_text(
            po_number=f"PO-{next(self._orders)}",
            vendor_sku=sku,
            quantity=str(kits),
        )
        record = self.backend.create_record(
            "rithum_in",
            {
                "exchange_file": base64.b64encode(text.encode("cp1252")),
                "rithum_partner_id": self.env.ref(
                    "edi_rithum_costco.rithum_partner_costco"
                ).id,
            },
        )
        order = self.env["sale.order"].browse()
        order = self.env["edi.rithum.costco.mapping.850"].create_orders(
            text,
            SCHEME,
            MAP_PATH,
            exchange_record=record if from_edi else None,
        )
        order.action_confirm()
        return order, order.picking_ids

    def _pack(self, picking, kits_per_package, weight=5.0):
        """Split the picked components into packages holding the given kits."""
        packages = [
            self.env["stock.package"].create({"shipping_weight": weight})
            for _ in kits_per_package
        ]
        for move in picking.move_ids:
            per_kit = PER_KIT.get(move.product_id.default_code)
            move.move_line_ids.unlink()
            for package, kits in zip(packages, kits_per_package, strict=True):
                if per_kit is None and package != packages[0]:
                    continue  # packaging material: all of it goes in the first box
                quantity = kits * per_kit if per_kit else move.product_uom_qty
                vals = move._prepare_move_line_vals(quantity=quantity)
                vals["result_package_id"] = package.id
                self.env["stock.move.line"].create(vals)
        picking.move_ids.picked = True
        return packages

    def _validate(self, picking, tracking=TRACKING, carrier=None):
        picking.write(
            {
                "carrier_id": (carrier or self.carrier).id,
                "carrier_tracking_ref": "+".join(tracking),
            }
        )
        with mock.patch.object(
            self.env.registry["edi.backend"], "exchange_send"
        ) as send:
            picking.with_context(
                skip_immediate=True, skip_backorder=True
            ).button_validate()
        return send

    def _text(self, record):
        return base64.b64decode(record.exchange_file).decode("cp1252")
