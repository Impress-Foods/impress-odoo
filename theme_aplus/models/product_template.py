import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_page_text_color = fields.Char()
    text_color = fields.Char()
    card_primary_color = fields.Char()
    card_secondary_color = fields.Char()
    card_text_color = fields.Char()

    hero_text_color = fields.Char()
    hero_background_color = fields.Char()

    hero_image = fields.Binary()
    hero_sticker = fields.Binary()
    card_image = fields.Binary()
    card_background_image = fields.Binary()
    suggestion_image = fields.Binary()
    minimalist_card_image = fields.Binary()

    carousel_order = fields.Integer()
    ingredients = fields.Html(translate=True)

    tab_1_title = fields.Char(translate=True)
    tab_2_title = fields.Char(translate=True)

    tab_1_text = fields.Html(translate=True)
    tab_2_text = fields.Html(translate=True)

    has_tvn = fields.Boolean(compute="_compute_has_tvn")

    show_water = fields.Boolean(default=True)
    show_fruits = fields.Boolean(default=True)
    show_maple = fields.Boolean(default=True)
    show_adq = fields.Boolean(default=True)

    @api.depends("product_variant_ids.nutrition_entry_ids")
    def _compute_has_tvn(self):
        for record in self:
            has_tvn = False
            for variant in record.product_variant_ids:
                has_tvn = bool(len(variant.nutrition_entry_ids))
                if has_tvn:
                    break
            record.has_tvn = has_tvn


class ProductVariant(models.Model):
    _inherit = "product.product"
    nutrition_entry_ids = fields.One2many("nutrition.fact.entry", "product_id")
    nutrition_facts_size = fields.Char()
    card_primary_color = fields.Char(related="product_tmpl_id.card_primary_color")
    card_secondary_color = fields.Char(related="product_tmpl_id.card_secondary_color")
    card_text_color = fields.Char(related="product_tmpl_id.card_text_color")
    card_background_image = fields.Binary(
        related="product_tmpl_id.card_background_image"
    )
    card_image = fields.Binary(related="product_tmpl_id.card_image")
    minimalist_card_image = fields.Binary(
        related="product_tmpl_id.minimalist_card_image"
    )
