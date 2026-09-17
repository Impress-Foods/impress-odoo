from odoo import api, models
from odoo.fields import Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _compute_display_name(self):
        res = super()._compute_display_name()
        if not self.env.context.get("global_vendor_search"):
            return res
        for product in self:
            vendor_codes = dict.fromkeys(
                code
                for code in product.variant_seller_ids.mapped("product_code")
                if isinstance(code, str)
            )
            if not vendor_codes:
                continue

            codes = (
                [product.default_code, *vendor_codes]
                if product.default_code
                else list(vendor_codes)
            )
            product.display_name = f"[{'] ['.join(codes)}] {product.name}"

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        res = super().name_search(name, domain, operator, limit)
        if not self.env.context.get("global_vendor_search", False):
            return res

        domain = Domain(domain or Domain.TRUE) & (
            Domain("seller_ids.product_code", operator, name)
            | Domain("variant_seller_ids.product_code", operator, name)
        )

        products = self.search_fetch(domain, ["display_name"], limit=limit)
        return list(dict.fromkeys(res + [(x.id, x.display_name) for x in products]))
