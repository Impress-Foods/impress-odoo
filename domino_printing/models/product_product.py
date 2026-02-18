import logging

from odoo import fields, models

from .domino import DominoAPI

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    domino_name = fields.Char()

    def action_domino_sync(self):
        dom = DominoAPI(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("domino_printing.api_endpoint"),
            self.env["ir.config_parameter"].sudo().get_param("domino_printing.api_key"),
        )
        for product in self:
            product._domino_sync(dom)

    def _domino_sync(self, domino_api: DominoAPI):
        self.ensure_one()
        domino_api.sync_product(self)
