from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_zip = fields.Char(related="partner_shipping_id.zip", stored=True)
