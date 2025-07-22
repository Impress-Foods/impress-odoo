import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    primary_color = fields.Char()
    secondary_color = fields.Char()
    text_color = fields.Char()

    background_image = fields.Binary()
    hero_image = fields.Binary()
