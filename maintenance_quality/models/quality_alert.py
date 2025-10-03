import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    maintenance_request_id = fields.Many2one(
        "maintenance.request", "Maintenance Request"
    )
