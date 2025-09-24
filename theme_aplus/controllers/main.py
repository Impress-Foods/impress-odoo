import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ThemeAPlus(http.Controller):
    @http.route("/theme_aplus/get_products", type="json", auth="public", website=True)
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
