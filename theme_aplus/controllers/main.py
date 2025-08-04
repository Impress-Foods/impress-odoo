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
        values_list = {
            i: values
            for i, values in enumerate(raw_values_list)  # type: ignore
        }
        return values_list
