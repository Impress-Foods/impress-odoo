import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    archived = fields.Boolean(default=False)

    def write(self, vals):
        res = super().write(vals)

        if "archived" in vals:
            skip_sync = self.env.context.get("skip_archive_sync")
            if not skip_sync:
                for doc in self:
                    if doc.attachment_id:
                        product_docs = self.env["product.document"].search(
                            [("ir_attachment_id", "=", doc.attachment_id.id)]
                        )
                        if product_docs:
                            product_docs.with_context(skip_archive_sync=True).write(
                                {"active": not vals["archived"]}
                            )

        return res

    def action_soft_archive(self):
        for rec in self:
            if not rec.archived:
                rec.archived = True

    def action_soft_unarchive(self):
        for rec in self:
            if rec.archived:
                rec.archived = False
