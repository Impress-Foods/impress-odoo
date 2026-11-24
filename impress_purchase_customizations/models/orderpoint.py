from odoo import fields, models


class Orderpoint(models.Model):
    _inherit = "stock.warehouse.orderpoint"

    vendor_id = fields.Many2one(related="supplier_id.partner_id")
