import logging

from odoo import fields, models

from .rate import Rate

_logger = logging.getLogger(__name__)


class WizardClickshipRates(models.TransientModel):
    _name = "wizard.clickship_rates"
    _description = "WizardClickshipRates"

    name = fields.Char()

    picking_id = fields.Many2one("stock.picking")

    rate_ids = fields.One2many("clickship.rate", "wizard_id")

    def choose_rate(self, rate: Rate) -> dict[str, str]:
        self.picking_id.clickship_service_id = rate.service_id
        return {"type": "ir.actions.act_window_close"}
