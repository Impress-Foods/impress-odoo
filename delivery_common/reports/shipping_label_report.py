import base64
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ReportShippingLabel(models.AbstractModel):
    _name = "report.delivery_common.report_shipping_label_view"
    _description = "Shipping labels (ZPL)"

    def _get_report_values(self, docids: list[int], data: dict) -> dict:
        pickings = self.env["stock.picking"].browse(docids)
        labels = []

        for picking in pickings:
            attachment = picking.shipping_label_attachment_id
            if attachment and attachment.mimetype != "application/pdf":
                data64 = attachment.datas
                string_data = base64.b64decode(data64).decode()
                labels.append(string_data)

        return {"docs": labels}
