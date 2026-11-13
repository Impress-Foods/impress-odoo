"""Inbound 850 interchange: one child record per purchase order."""

import base64

from odoo import api, models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord
from odoo.addons.edi_x12.x12.reading import split_transactions

ORDER_TYPE = "costco_850_in"
MAPPING_850 = "edi.rithum.costco.mapping.850"


class EdiRithumCostcoSplitter850(models.AbstractModel):
    """Splits a validated interchange of 850s into one record per order.

    The framework keeps one state per record and rolls back everything a failing
    record did. With one record per order, an unknown product or an already open
    PO number stops that order only: it shows on its own record, which can be
    retried once fixed, and the other orders of the file go through.
    """

    _name = "edi.rithum.costco.splitter.850"
    _description = "Costco 850 interchange splitter"

    @api.model
    def process(self, exchange_record: EDIExchangeRecord) -> None:
        """Validate the file, then create and queue one child record per order.

        The 997 stays on this record and covers the whole file; the children have
        an exchange type with no acknowledgment.
        """
        text = exchange_record._get_file_content()
        backend = exchange_record.backend_id
        self.env["edi.exchange.type"].x12_validate(
            text, exchange_record.rithum_partner_id.map_path()
        )
        self.env[MAPPING_850]._check_environment(text, backend.x12_production)
        if self._children(exchange_record):
            return  # processed before: the orders are already on their way
        order_type = self.env["edi.exchange.type"].search(
            [("code", "=", ORDER_TYPE)], limit=1
        )
        name = exchange_record.exchange_filename
        for number, order_text in enumerate(split_transactions(text), start=1):
            child = backend.create_record(
                ORDER_TYPE,
                {
                    "parent_id": exchange_record.id,
                    "rithum_partner_id": exchange_record.rithum_partner_id.id,
                    "x12_document": "850",
                    "exchange_filename": f"{name}#{number}",
                    "exchange_file": base64.b64encode(
                        order_text.encode(order_type.encoding)
                    ),
                    "edi_exchange_state": "input_received",
                },
            )
            child.action_exchange_receive_process_chained()

    def _children(self, exchange_record: EDIExchangeRecord) -> EDIExchangeRecord:
        return self.env["edi.exchange.record"].search(
            [
                ("parent_id", "=", exchange_record.id),
                ("type_id.code", "=", ORDER_TYPE),
            ],
            limit=1,
        )
