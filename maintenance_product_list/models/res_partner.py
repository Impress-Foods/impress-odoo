import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    product_count = fields.Integer(compute="_compute_product_count")

    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(
                self.env["product.supplierinfo"].search([("partner_id", "=", rec.id)])
            )

    def action_view_products(self):
        self.ensure_one()
        sup_info = self.env["product.supplierinfo"].search(
            [("partner_id", "=", self.id)]
        )
        variants = sup_info.mapped("product_id")
        templates = sup_info.mapped("product_tmpl_id")
        variants_from_templates = templates.mapped("product_variant_ids")
        product_ids = (variants | variants_from_templates).mapped("id")

        action = {
            "name": self.env._("Vendor's Products"),
            "type": "ir.actions.act_window",
            "view_mode": "list,form",
            "res_model": "product.product",
            "domain": [("id", "in", product_ids)],
        }
        return action
