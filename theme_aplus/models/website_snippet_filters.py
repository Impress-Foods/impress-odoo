import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class WebsiteSnipperFilter(models.Model):
    _inherit = "website.snippet.filter"

    @api.model
    def _get_products(self, mode, context):
        return super()._get_products(mode, context)

    @api.model
    def _get_products_alternative_products_templates(
        self, website, limit, domain, context
    ):
        variants = self._get_products_alternative_products(
            website, limit, domain, context
        )
        product_templates = variants.mapped("product_tmpl_id")
        return product_templates
