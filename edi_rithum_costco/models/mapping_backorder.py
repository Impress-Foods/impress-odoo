"""Outbound 856 that backorders: units of a delivery that cannot ship yet."""

from datetime import timedelta
from decimal import Decimal

from odoo import api, fields, models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12 import outbound
from odoo.addons.stock.models.stock_picking import StockPicking

from ..documents import tset_856

LEAD_DAYS = 5  # a backorder is promised this many days from today


class EdiRithumCostcoMappingBackorder(models.AbstractModel):
    _name = "edi.rithum.costco.mapping.backorder"
    _description = "Costco 856 Backorder"

    @api.model
    def generate(self, exchange_record: EDIExchangeRecord) -> str:
        """The backorder message of the delivery this record is linked to."""
        picking = exchange_record.record
        order = picking.sale_id
        shipments = self.env["edi.rithum.costco.mapping.856"]
        confirmation = tset_856.ShipmentConfirmation(
            # The delivery's own name is what its shipment confirmation will carry.
            shipment_id=f"{picking.name}-BO",
            po_number=order.client_order_ref or "",
            created_at=shipments._local(order.company_id, fields.Datetime.now()),
            backordered=tuple(self._items(picking)),
        )
        body = tset_856.build_body(confirmation)
        envelope = shipments._envelope(exchange_record, order)
        tree = outbound.interchange(envelope, body, tset_856.TSET, "0001")
        return outbound.render(tree, exchange_record.type_id.x12_map_path())

    def _items(self, picking: StockPicking) -> list[tset_856.BackorderedItem]:
        """Each Costco line of the delivery, with the units still owed on it."""
        shipments = self.env["edi.rithum.costco.mapping.856"]
        promised = shipments._local_midnight(
            picking.company_id,
            fields.Date.context_today(picking) + timedelta(days=LEAD_DAYS),
        )
        items = []
        for line in picking.move_ids.sale_line_id.filtered("costco_sku"):
            owed = line.product_uom_qty - line.qty_delivered
            if owed > 0:
                items.append(
                    tset_856.BackorderedItem(
                        line_number=line.edi_id or "",
                        vendor_sku=line.product_id.default_code or "",
                        buyer_sku=line.costco_sku,
                        quantity=Decimal(str(owed)),
                        promised_at=promised,
                    )
                )
        return items
