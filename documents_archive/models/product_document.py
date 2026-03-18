import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ProductDocument(models.Model):
    _inherit = "product.document"

    def write(self, vals):
        res = super().write(vals)

        if "active" in vals:
            skip_sync = self.env.context.get("skip_archive_sync")
            if not skip_sync:
                for prod_doc in self:
                    if prod_doc.ir_attachment_id:
                        docs = self.env["documents.document"].search(
                            [("attachment_id", "=", prod_doc.ir_attachment_id.id)]
                        )
                        if docs:
                            docs.with_context(skip_archive_sync=True).write(
                                {"archived": not vals["active"]}
                            )

        return res

    def action_soft_archive(self):
        for rec in self:
            if rec.active:
                rec.active = False

    def action_soft_unarchive(self):
        for rec in self:
            if not rec.active:
                rec.active = True
