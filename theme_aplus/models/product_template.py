import logging

from odoo import fields, models

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

    carousel_order = fields.Integer()
    ingredients = fields.Html(translate=True)


class ProductVariant(models.Model):
    _inherit = "product.product"
    nutrition_entry_ids = fields.One2many("nutrition.fact.entry", "product_id")
    nutrition_facts_size = fields.Char()
