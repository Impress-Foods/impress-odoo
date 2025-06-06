import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    sequence = fields.Char(string="Sequence", default="New")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "sequence" not in vals or vals["sequence"] == _("New"):
                vals["sequence"] = self.env["ir.sequence"].next_by_code(
                    "maintenance.request"
                ) or _("New")
        return super().create(vals_list)
