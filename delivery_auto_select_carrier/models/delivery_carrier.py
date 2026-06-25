from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    priority = fields.Integer()
    can_be_auto_selected = fields.Boolean()
