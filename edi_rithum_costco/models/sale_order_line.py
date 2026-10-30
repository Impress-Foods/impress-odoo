from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    costco_sku = fields.Char(
        string="Costco SKU",
        readonly=True,
        copy=False,
        help="Costco's own item number for the line (PO107 of the 850). Our "
        "item number is the product's internal reference.",
    )
