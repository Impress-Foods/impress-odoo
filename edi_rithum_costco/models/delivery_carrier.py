from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    costco_shipping_method = fields.Char(
        help="Costco's code for this carrier and service (TD505 of the shipment "
        "confirmation), for example UPSN_CG. CommerceHub supplies the list.",
    )
