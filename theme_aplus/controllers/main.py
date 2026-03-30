import logging

from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.variant import WebsiteSaleVariantController

_logger = logging.getLogger(__name__)


class ThemeAPlus(http.Controller):
    @http.route("/theme_aplus/get_products", type="jsonrpc", auth="public", website=True)
    def get_products(self, filter_id, search_domain=None):
        dynamic_filter = (
            request.env["website.snippet.filter"]
            .sudo()
            .search([("id", "=", filter_id)] + request.website.website_domain())
        )
        raw_values_list = dynamic_filter._prepare_values(search_domain=search_domain)
        if isinstance(raw_values_list, list):
            raw_values_list.sort(key=lambda x: x.get("carousel_order", 0))
            values_list = {i: values for i, values in enumerate(raw_values_list)}

            return values_list
        raise ValueError("Invalid filter")


class VariantAplus(WebsiteSaleVariantController):
    @http.route(
        "/website_sale/get_combination_info",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def get_combination_info_website(
        self,
        product_template_id,
        product_id,
        combination,
        add_qty,
        parent_combination=None,
        **kwargs,
    ):
        res = super().get_combination_info_website(
            product_template_id,
            product_id,
            combination,
            add_qty,
            parent_combination,
            **kwargs,
        )
        product_template = request.env["product.template"].browse(
            product_template_id and int(product_template_id)
        )

        combination_info = product_template._get_combination_info(
            combination=request.env["product.template.attribute.value"].browse(
                combination
            ),
            product_id=product_id and int(product_id),
            add_qty=add_qty and float(add_qty) or 1.0,
            parent_combination=request.env["product.template.attribute.value"].browse(
                parent_combination
            ),
        )

        res["tvn"] = request.env["ir.ui.view"]._render_template(
            "theme_aplus.tvn",
            values={
                "product": product_template,
                "product_variant": request.env["product.product"].browse(
                    combination_info["product_id"]
                ),
                "website": request.env["website"].get_current_website(),
            },
        )
        return res
