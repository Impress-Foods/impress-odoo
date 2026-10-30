"""Outbound 856 that only cancels: units of an order we will not ship."""

from decimal import Decimal

from odoo import api, fields, models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12 import outbound

from ..documents import tset_856
from ..wizards.cancellation import EdiRithumCostcoCancellation


class EdiRithumCostcoMappingCancel(models.AbstractModel):
    _name = "edi.rithum.costco.mapping.cancel"
    _description = "Costco 856 Cancellation"

    @api.model
    def generate(self, exchange_record: EDIExchangeRecord) -> str:
        """The cancellation message of the cancellation this record is linked to."""
        cancellation = exchange_record.record
        order = cancellation.order_id
        shipments = self.env["edi.rithum.costco.mapping.856"]
        confirmation = tset_856.ShipmentConfirmation(
            shipment_id=cancellation.name,
            po_number=order.client_order_ref or "",
            created_at=shipments._local(order.company_id, fields.Datetime.now()),
            cancelled=tuple(self._items(cancellation)),
        )
        body = tset_856.build_body(confirmation)
        envelope = shipments._envelope(exchange_record, order)
        tree = outbound.interchange(envelope, body, tset_856.TSET, "0001")
        return outbound.render(tree, exchange_record.type_id.x12_map_path())

    def _items(
        self, cancellation: EdiRithumCostcoCancellation
    ) -> list[tset_856.CancelledItem]:
        reason = cancellation.reason_id.code
        return [
            tset_856.CancelledItem(
                line_number=line.sale_line_id.edi_id or "",
                vendor_sku=line.product_id.default_code or "",
                buyer_sku=line.sale_line_id.costco_sku or "",
                quantity=Decimal(str(line.quantity)),
                reason=reason,
                note=cancellation.note or "",
            )
            for line in cancellation.line_ids.filtered(lambda line: line.quantity)
        ]
