import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ObiboxCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("obibox", "Obibox")],
        ondelete={
            "obibox": lambda recs: recs.write(
                {"delivery_type": "fixed", "fixed_price": 0}
            )
        },
    )

    obibox_api_key = fields.Char(string="Obibox Key", groups="base.group_system")

    def obibox_rate_shipment(self, order) -> dict:
        # response:
        # {
        # 'success': Bool,
        # 'price' : float,
        # 'error_message': string | False,
        # 'warning_message': string | False
        # }

        return {}

    def obibox_send_shipping(self, pickings) -> list:
        return []

    def obibox_get_tracking_link(self, picking) -> str:
        return ""

    def obibox_cancel_shipment(self, picking) -> None:
        return

    def _obibox_get_default_custom_package_code(self) -> str:
        return ""
