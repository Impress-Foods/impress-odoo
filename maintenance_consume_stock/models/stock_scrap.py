import logging

from odoo import api, fields, models
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

    @api.ondelete(at_uninstall=False)
    def _unlink_except_linked(self):
        for record in self:
            if record.maintenance_request_id and record.state == "done":
                raise UserError(
                    self.env._(
                        "Cannot unlink a scrap move that is done and "
                        "assigned to a maintenance request"
                    )
                )

    def action_view_maintenance_request(self):
        self.ensure_one()

        action = {
            "name": self.env._("Maintenance Request"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "maintenance.request",
            "res_id": self.maintenance_request_id.id,
        }

        return action
