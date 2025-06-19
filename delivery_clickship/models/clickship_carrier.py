import logging

from odoo import fields, models

from .clickship_request import ClickshipProvider

_logger = logging.getLogger(__name__)


class ClickShipCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("clickship", "Click Ship")],
        ondelete={
            "clickship": lambda recs: recs.write(
                {"delivery_type": "fixed", "fixed_price": 0}
            )
        },
    )

    clickship_api_key = fields.Char(string="Click Ship Key", groups="base.group_system")

    def clickship_rate_shipment(self, order) -> dict:
        sr = ClickshipProvider(self.log_xml)
        res = sr.get_rate(order)  # noqa

        return {}

    def clickship_send_shipping(self, pickings) -> list:
        return []

    def clickship_get_tracking_link(self, picking) -> str:
        return ""

    def clickship_cancel_shipment(self, picking) -> None:
        return

    def _clickship_get_default_custom_package_code(self) -> str:
        return ""
