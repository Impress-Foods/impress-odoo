import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    domino_api_endpoint = fields.Char(config_parameter="domino_printing.api_endpoint")
    domino_api_key = fields.Char(config_parameter="domino_printing.api_key")
