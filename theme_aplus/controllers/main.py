import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ThemeAPlus(http.Controller):
    @http.route(
        "/theme_aplus/aplus_product_carousel", type="http", auth="public", website=True
    )
    def aplus_product_carousel(self):
        return http.request.render("theme_aplus.aplus_product_carousel")

    @http.route("/theme_aplus/get_products", type="json", auth="public", website=True)
    def get_products(self, filter_id):
        dynamic_filter = (
            request.env["website.snippet.filter"]
            .sudo()
            .search([("id", "=", filter_id)] + request.website.website_domain())
        )
        raw_values_list = dynamic_filter._prepare_values()

        values_list = {
            i: self._process_values(values)
            for i, values in enumerate(raw_values_list)  # type: ignore
        }
        return values_list

    def _process_values(self, data):
        values = {
            "display_name": data["display_name"],
            "image_512": data["image_512"],
            "product_id": data["product_id"],
        }
        return values
