import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    scrap_ids = fields.One2many(
        comodel_name="stock.scrap",
        inverse_name="maintenance_request_id",
        string="Scraps",
    )
    scrap_count = fields.Integer(compute="_compute_scrap_count", store=True)
    all_scraps_done = fields.Boolean(compute="_compute_all_scraps_done", store=True)

    def unlink(self):
        for record in self:
            if record.scrap_ids:
                if any([state == "done" for state in record.scrap_ids.mapped("state")]):
                    raise UserError(
                        _("Cannot delete a maintenance request with done scrap moves")
                    )
        return super().unlink()

    @api.depends("scrap_ids")
    def _compute_scrap_count(self):
        for record in self:
            record.scrap_count = len(record.scrap_ids)

    def _consume_parts(self):
        for record in self:
            for scrap_move in record.scrap_ids:
                if scrap_move.state != "done":
                    scrap_move.do_scrap()

    @api.depends("scrap_ids.state", "scrap_count")
    def _compute_all_scraps_done(self):
        for record in self:
            record.all_scraps_done = all(
                scrap.state == "done" for scrap in record.scrap_ids
            )

    def action_consume_parts(self):
        for record in self:
            record._consume_parts()

    def action_view_scrap_move(self):
        self.ensure_one()
        if len(self.scrap_ids) == 1:
            action = {
                "name": _("Scrap Moves"),
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "stock.scrap",
                "res_id": self.scrap_ids[0].id,
            }
        else:
            action = {
                "name": _("Scrap Moves"),
                "type": "ir.actions.act_window",
                "view_mode": "tree,form",
                "res_model": "stock.scrap",
                "domain": [("id", "in", [scrap.id for scrap in self.scrap_ids])],
            }

        return action
