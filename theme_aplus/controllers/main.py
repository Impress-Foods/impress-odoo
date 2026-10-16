import json
import logging

from odoo import http
from odoo.fields import Domain
from odoo.http import request

from odoo.addons.portal.controllers.web import Home
from odoo.addons.product.models.product_template import ProductTemplate
from odoo.addons.website_sale.controllers.main import TableCompute, WebsiteSale
from odoo.addons.website_sale.models.product_public_category import (
    ProductPublicCategory,
)

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


class ThemeAPlusWebsiteSale(WebsiteSale):
    """Split the shop product grid by public category.

    Core deliberately keeps two concerns apart: the product order (chosen by the
    "Sort By" option, applied before pagination) and the product size
    (``website_size_x`` / ``website_size_y``, packed into a grid by
    :class:`~odoo.addons.website_sale.controllers.main.TableCompute`).

    This override only re-orders the products of the current page so that the
    ones sharing a public category end up contiguous, then hands that new order
    back to ``TableCompute``. Each product therefore keeps core's own ``x``/``y``
    spans: the sizing logic is never reimplemented here.
    """

    def _get_additional_shop_values(self, values: dict, **kwargs) -> dict:
        """Add the category-grouped grid to the shop template values.

        Overrides
        :meth:`~odoo.addons.website_sale.controllers.main.WebsiteSale._get_additional_shop_values`.
        """
        additional_values = super()._get_additional_shop_values(values, **kwargs)
        if request.website.is_view_active("theme_aplus.group_by_categories"):
            additional_values["bins"] = self._group_bins_by_category(values)
        return additional_values

    @staticmethod
    def _get_primary_category(product: ProductTemplate) -> ProductPublicCategory:
        """Return the category a product is grouped under.

        A product may belong to several public categories; the one with the
        lowest ``sequence`` wins, ``id`` breaking ties so that the result stays
        stable. Products without any public category return an empty recordset.
        """
        return product.public_categ_ids.sorted(
            lambda category: (category.sequence, category.id)
        )[:1]

    @staticmethod
    def _group_bins_by_category(values: dict) -> list:
        """Re-order core's grid cells so that each category forms one block.

        :param dict values: the shop template values, must contain ``bins`` (the
            grid packed by core), ``ppg`` and ``ppr``.
        :return: a new ``bins`` structure packed exactly the way core packs it.
            The first cell of every category block carries an extra
            ``group_header`` key holding the category name to display. Products
            without any category are grouped last and get no header.
        """
        bins = values["bins"]
        cells = [cell for row in bins for cell in row if cell]
        if not cells:
            return bins

        # Map each product to the `(sequence, id, name)` of its primary category,
        # or to None when it has none.
        categories = {}
        for cell in cells:
            category = ThemeAPlusWebsiteSale._get_primary_category(cell["product"])
            categories[cell["product"].id] = (
                (category.sequence, category.id, category.name) if category else None
            )

        def _sort_key(cell: dict) -> tuple:
            category = categories[cell["product"].id]
            # Uncategorised products are pushed to the end.
            return (category is None, category or (0, 0, ""))

        ordered_products = cells[0]["product"].browse(
            [cell["product"].id for cell in sorted(cells, key=_sort_key)]
        )
        grouped_bins = TableCompute().process(
            ordered_products, values["ppg"], values["ppr"]
        )

        # A single category means there is nothing to separate.
        show_headers = (
            len({category[1] for category in categories.values() if category}) > 1
        )

        current_category_id = None
        for row in grouped_bins:
            for cell in row:
                if not cell:
                    continue
                category = categories[cell["product"].id]
                category_id = category and category[1]
                if category_id == current_category_id:
                    continue
                current_category_id = category_id
                if show_headers and category:
                    cell["group_header"] = category[2]
        return grouped_bins
