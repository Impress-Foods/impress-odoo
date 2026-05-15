import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ClickshipPaymentMethod(models.Model):
    _name = "clickship.payment_method"
    _description = "ClickshipPaymentMethod"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    delivery_carrier_id = fields.Many2one(comodel_name="delivery.carrier")
