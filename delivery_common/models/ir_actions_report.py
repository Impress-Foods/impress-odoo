import base64
import io

from odoo import models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == "delivery_common.report_shipping_label_pdf":
            return self._render_stored_shipping_label_pdf(res_ids), "pdf"
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_stored_shipping_label_pdf(self, res_ids):
        if isinstance(res_ids, int):
            res_ids = [res_ids]
        pickings = self.env["stock.picking"].browse(res_ids or [])
        streams = []

        for picking in pickings:
            attachment = picking.shipping_label_attachment_id
            if attachment and attachment.mimetype == "application/pdf":
                streams.append(io.BytesIO(base64.b64decode(attachment.datas)))

        if not streams:
            raise UserError(
                self.env._(
                    "No PDF shipping label is available for the selected pickings."
                )
            )

        if len(streams) == 1:
            return streams[0].getvalue()

        with self._merge_pdfs(streams) as merged_pdf:
            return merged_pdf.getvalue()
