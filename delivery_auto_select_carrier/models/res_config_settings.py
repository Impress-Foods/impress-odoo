from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    auto_select_carrier_domain = fields.Char(
        config_parameter="delivery_auto_select_carrier.domain"
    )
