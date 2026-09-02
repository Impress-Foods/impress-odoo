import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ErpProduct(models.Model):
    _name = "erp.product"
    _description = "External Product Mapping"
    _rec_name = "external_name"

    product_id = fields.Many2one(comodel_name="product.product")

    external_id = fields.Char(required=True)
    external_name = fields.Char(required=True)

    backend_id = fields.Many2one(comodel_name="erp.backend", required=True)

    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug(self.env.context)
        return super().create(vals_list)
