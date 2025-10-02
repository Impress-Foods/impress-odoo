import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    maintenance_request_id = fields.Many2one(
        comodel_name="maintenance.request",
        string="Maintenance Request",
        ondelete="cascade",
    )

    maintenance_equipement_id = fields.Many2one(
        related="maintenance_request_id.equipment_id",
        string="Equipment",
        store=True,
        depends=["maintenance_request_id", "maintenance_request_id.equipment_id"],
    )

    product_vendor_code = fields.Char(related="product_id.vendor_code")

    def unlink(self):
        if self.maintenance_request_id and self.state == "done":
            raise UserError(
                _(
                    "Cannot unlink a scrap move that is done and "
                    "assigned to a maintenance request"
                )
            )
        return super().unlink()

    def action_view_maintenance_request(self):
        self.ensure_one()

        action = {
            "name": _("Maintenance Request"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "maintenance.request",
            "res_id": self.maintenance_request_id.id,
        }

        return action
