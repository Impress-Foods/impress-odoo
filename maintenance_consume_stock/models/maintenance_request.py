from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    scrap_ids = fields.One2many(
        comodel_name="stock.scrap",
        inverse_name="maintenance_request_id",
        string="Scraps",
    )
    scrap_count = fields.Integer(compute="_compute_scrap_count", store=True)
    has_scraps_to_validate = fields.Boolean(compute="_compute_has_scraps_to_validate")

    @api.ondelete(at_uninstall=False)
    def _unlink_except_linked(self):
        for record in self:
            if "done" in record.scrap_ids.mapped("state"):
                raise UserError(
                    self.env._(
                        "Cannot delete a maintenance request with done scrap moves"
                    )
                )

    @api.depends("scrap_ids")
    def _compute_scrap_count(self):
        for record in self:
            record.scrap_count = len(record.scrap_ids)

    @api.depends("scrap_ids", "scrap_ids.state")
    def _compute_has_scraps_to_validate(self):
        for record in self:
            record.has_scraps_to_validate = "draft" in record.scrap_ids.mapped("state")

    def _consume_parts(self):
        for scrap_move in self.scrap_ids.filtered_domain(Domain("state", "!=", "done")):
            action = scrap_move.action_validate()
            if isinstance(action, dict):
                return action

    def action_consume_parts(self):
        return self._consume_parts()

    def action_view_scrap_move(self):
        self.ensure_one()
        action = {
            "name": self.env._("Scrap Moves"),
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "res_model": "stock.scrap",
            "domain": Domain("id", "in", self.scrap_ids.ids),
        }
        if len(self.scrap_ids) == 1:
            action["res_id"] = self.scrap_ids.id
            action["view_mode"] = "form"
        return action
