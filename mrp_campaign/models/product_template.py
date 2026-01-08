import logging
from pprint import pformat

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.mrp.models.mrp_bom import MrpBom
from odoo.addons.product.models.product_product import ProductProduct

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_campaign_manufactured = fields.Boolean()
    is_campaign_anchor = fields.Boolean(
        help="This product can be used as an anchor for manufacturing campaigns.",
    )
    mrp_max_batch_size = fields.Integer()
    campaign_bucket_size = fields.Integer(string="Bucket Size", default=1)
    campaign_bucket_type = fields.Selection(
        selection=[("day", "Day"), ("week", "Week"), ("month", "Month")], default="day"
    )


class ProductProductModel(models.Model):
    _inherit = "product.product"

    def _get_anchor_product(self) -> ProductProduct:
        self.ensure_one()

        if self.product_tmpl_id.is_campaign_anchor:
            return self

        bom_ids: MrpBom = self.bom_ids.filtered_domain([("type", "=", "normal")])

        if not bom_ids:
            return self.env["product.product"]

        anchors: list[ProductProduct] = (
            bom_ids.mapped("bom_line_ids")
            .mapped("product_id")
            .mapped(lambda p: p._get_anchor_product())
        )
        _logger.warning(pformat([product.display_name for product in anchors]))

        if len(anchors) == 1:
            return anchors
        else:
            raise ValidationError(
                _(f"Could not find anchor product. Expected 1, found {len(anchors)}")
            )
