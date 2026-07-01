import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _compute_display_name(self):
        res = super()._compute_display_name()
        if self.env.context.get("global_vendor_search", False):
            for product in self:
                supplier_rules = product.seller_ids + product.variant_seller_ids
                if supplier_rules:
                    vendor_codes = [
                        x
                        for x in set(supplier_rules.mapped("product_code"))
                        if isinstance(x, str)
                    ]
                    if vendor_codes:
                        codes = []
                        if product.default_code:
                            codes.append(product.default_code)
                        codes += vendor_codes
                        formatted_codes = "] [".join(codes)
                        product.display_name = f"[{formatted_codes}] {product.name}"
        return res

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        res = super().name_search(name, domain, operator, limit)
        if self.env.context.get("global_vendor_search", False):
            domain = [
                "|",
                ("seller_ids.product_code", "ilike", name),
                ("variant_seller_ids.product_code", "ilike", name),
            ]
            products = self.env["product.product"].search(domain)
            add_results = [(x.id, x.display_name) for x in products]
            res += add_results
            res = list(set(res))
        return res
