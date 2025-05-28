# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get("global_vendor_search", False):
            for product in self:
                supplier_rules = product.seller_ids + product.variant_seller_ids
                if supplier_rules:
                    vendor_codes = [
                        x
                        for x in set(supplier_rules.mapped("product_code"))
                        if type(x) is str
                    ]
                    if vendor_codes:
                        product.display_name = f"[{product.default_code}-{'-'.join(vendor_codes)}] {product.name}"

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        res = super().name_search(name, args, operator, limit)
        if self.env.context.get("global_vendor_search", False):
            domain = [
                "|",
                ("seller_ids.product_code", "ilike", name),
                ("variant_seller_ids.product_code", "ilike", name),
            ]
            products = self.env["product.product"].search(domain)
            add_results = [(x.id, x.display_name) for x in products]
            _logger.warning(add_results)
            res += add_results
            res = list(set(res))
        return res
