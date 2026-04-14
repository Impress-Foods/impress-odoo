import json
import logging

from odoo import http
from odoo.fields import Domain
from odoo.http import request

from odoo.addons.portal.controllers.web import Home

_logger = logging.getLogger(__name__)


class ThemeAPlus(Home):
    @http.route(
        "/window_carousel/products",
        type="jsonrpc",
        auth="public",
        website=True,
        readonly=True,
    )
    def get_window_carousel_products(self, limit=16, tag_ids=None, **kwargs):
        Website = request.env["website"]
        domain = Website.get_current_website().website_domain()
        domain &= Domain("hero_image", "!=", False)
        domain &= Domain("is_published", "=", True)
        if tag_ids:
            if isinstance(tag_ids, str):
                tag_ids = [t["id"] for t in json.loads(tag_ids)]
            if tag_ids:
                domain &= Domain("product_tag_ids", "in", tag_ids)
        products = (
            request.env["product.template"]
            .sudo()
            .search(domain, order="carousel_order asc", limit=limit)
        )
        result = []
        for p in products:
            result.append(
                {
                    "id": p.id,
                    "display_name": p.display_name,
                    "hero_image": Website.image_url(p, "hero_image"),
                    "hero_background_color": p.hero_background_color or "#f7f9fc",
                    "hero_text_color": p.hero_text_color or "#000000",
                    "hero_sticker": Website.image_url(p, "hero_sticker")
                    if p.hero_sticker
                    else "",
                    "product_url": p.website_url or f"/shop/product/{p.id}",
                }
            )
        return result
