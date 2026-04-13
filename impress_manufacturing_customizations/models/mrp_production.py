import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    sequence = fields.Integer()
    product_category_id = fields.Many2one(
        "product.category",
        related="product_tmpl_id.categ_id",
        store=True,
        depends=["product_tmpl_id"],
    )
