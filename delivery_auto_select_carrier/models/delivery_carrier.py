import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    priority = fields.Integer()
    can_be_auto_selected = fields.Boolean()
