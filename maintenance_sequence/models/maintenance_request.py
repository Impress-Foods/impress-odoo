import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    sequence = fields.Char()

    def _compute_display_name(self):
        for record in self:
            if record.sequence != _("New"):
                record.display_name = f"{record.sequence} - {record.name}"
            else:
                record.display_name = record.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["sequence"] = self.env["ir.sequence"].next_by_code(
                "maintenance_request"
            )
        return super().create(vals_list)
