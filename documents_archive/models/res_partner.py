import logging

from odoo import models

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _inherit = "res.partner"

    def action_see_documents(self):
        self.ensure_one()
        action = super().action_see_documents()
        return action

    def _compute_document_count(self):
        read_group_var = self.env["documents.document"]._read_group(
            [("partner_id", "in", self.ids), ("archived", "=", False)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )

        document_count_dict = {partner.id: count for partner, count in read_group_var}
        for record in self:
            record.document_count = document_count_dict.get(record.id, 0)
