import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class WizardClickship_rates(models.TransientModel):
    _name = "wizard.clickship_rates"
    _description = _("WizardClickship_rates")

    name = fields.Char()

    picking_id = fields.Many2one("stock.picking")

    rate_ids = fields.One2many("clickship.rate", "wizard_id")

    def choose_rate(self, rate) -> dict:
        self.picking_id.clickship_service_id = rate.service_id
        return {"type": "ir.actions.act_window_close"}
