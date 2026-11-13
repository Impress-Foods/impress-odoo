from odoo import models

from odoo.addons.edi_core_oca.models.edi_exchange_record import EDIExchangeRecord

SHIPMENT_TYPE = "costco_856_out"
BACKORDER_TYPE = "costco_backorder_out"


class EdiExchangeRecord(models.Model):
    _inherit = "edi.exchange.record"

    def _x12_send_blockers(self) -> EDIExchangeRecord:
        """Extends edi.exchange.record._x12_send_blockers.

        Costco must get the backorder notice of a delivery before its shipment
        confirmation: the notice is what tells it the missing units are coming.
        The jobs of both may run at the same time, so the confirmation waits
        for the notices of the backorders of its delivery whose upload is still queued.
        """
        blockers = super()._x12_send_blockers()
        if self.type_id.code != SHIPMENT_TYPE or self.model != "stock.picking":
            return blockers
        backorders = self.env["stock.picking"].search(
            [("backorder_id", "=", self.res_id)]
        )
        return blockers | backorders.exchange_record_ids.filtered(
            lambda r: r.type_id.code == BACKORDER_TYPE and r._x12_send_job_pending()
        )
