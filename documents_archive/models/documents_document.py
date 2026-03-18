import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    archived = fields.Boolean(default=False)

    def is_archived(self):
        return self.archived

    def action_soft_archive(self):
        if not self.archived:
            self.archived = True
        if self.attachment_id:
            matching_attachment = self._get_matching_attachment()
            if matching_attachment:
                matching_attachment.active = False

    def action_soft_unarchive(self):
        if self.archived:
            self.archived = False
        if self.attachment_id:
            matching_attachment = self._get_matching_attachment()
            if matching_attachment:
                matching_attachment.active = True

    def _get_matching_attachment(self):
        records = self.env["product.document"].search(
            [
                ("ir_attachment_id", "=", self.attachment_id.id),
                ("active", "in", [True, False]),
            ]
        )
        if records:
            return records[0]
        else:
            return None
