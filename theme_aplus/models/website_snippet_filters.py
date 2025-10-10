import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class WebsiteSnipperFilter(models.Model):
    _inherit = "website.snippet.filter"

    @api.model
    def _get_products(self, mode, context):
        _logger.error(mode)
        return super()._get_products(mode, context)

    @api.model
    def _get_products_alternative_products_templates(
        self, website, limit, domain, context
    ):
        _logger.warning("_get_products_alternative_products_templates")
        variants = self._get_products_alternative_products(
            website, limit, domain, context
        )
        product_templates = variants.mapped("product_tmpl_id")
        _logger.warning(context.get("dynamic_filter"))
        return product_templates
