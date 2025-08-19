from odoo import fields, models


class NutritionFactEntry(models.Model):
    _name = "nutrition.fact.entry"
    _description = "Nutrition fact table entry"

    name = fields.Char(required=True, translate=True)
    value = fields.Char()
    product_id = fields.Many2one("product.product", required=True)
    sequence = fields.Integer()
