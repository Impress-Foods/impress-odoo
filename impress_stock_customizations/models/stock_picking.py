from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    minimum_shelf_life = fields.Integer(related="partner_id.minimum_shelf_life")
