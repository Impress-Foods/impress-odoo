import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_campaign_anchor = fields.Boolean(
        help="This product can be used as an anchor for manufacturing campaigns.",
    )
    mrp_max_batch_size = fields.Integer()
    campaign_buffer_percent = fields.Float()


class ProductProductModel(models.Model):
    _inherit = "product.product"

    anchor_product_id = fields.Many2one(
        "product.product", recursive=True, store=True, compute="_compute_anchor_product"
    )
    is_campaign_anchor = fields.Boolean(
        related="product_tmpl_id.is_campaign_anchor",
    )

    @api.depends(
        "bom_ids",
        "bom_ids.bom_line_ids",
        "bom_ids.bom_line_ids.product_id",
        "bom_ids.bom_line_ids.product_id.anchor_product_id",
    )
    def _compute_anchor_product(self):
        for rec in self:
            rec.anchor_product_id = self._get_root_anchor(rec)

    def _get_root_anchor(self, product, visited=None):
        if visited is None:
            visited = set()
        if product.id in visited:
            return self.env["product.product"]
        visited.add(product.id)

        if product.is_campaign_anchor:
            return product

        bom = self.env["mrp.bom"]._bom_find(product)[product]
        if not bom or bom.type != "normal":
            return self.env["product.product"]

        anchors_found = set()
        for line in bom.bom_line_ids:
            anchor = self._get_root_anchor(line.product_id, visited)
            if anchor:
                anchors_found.add(anchor)

        if len(anchors_found) == 1:
            return list(anchors_found)[0]

        elif len(anchors_found) > 1:
            _logger.debug("Multiple anchors found")
            return self.env["product.product"]

        # 6. Default: No anchor found in any lineage
        _logger.debug("No anchors found")
        return self.env["product.product"]
