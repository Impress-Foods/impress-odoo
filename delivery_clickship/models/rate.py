import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class Rate(models.TransientModel):
    _name = "clickship.rate"
    _description = "Rate"
    _rec_name = "carrier_name"

    _order = "total asc"

    wizard_id = fields.Many2one("wizard.clickship_rates")

    carrier_name = fields.Char()
    service_name = fields.Char()
    service_id = fields.Char()

    transit_time = fields.Integer()
    transit_time_valid = fields.Boolean()

    total = fields.Monetary()
    currency_id = fields.Many2one("res.currency")

    def button_choose(self) -> None:
        self.wizard_id.choose_rate(self)
