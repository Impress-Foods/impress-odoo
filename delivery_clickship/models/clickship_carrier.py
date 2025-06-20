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
    clickship_contact = fields.Many2one("hr.employee")

    def clickship_rate_shipment(self, order) -> dict:
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        res = sr.get_rate(order, self.clickship_contact)
        price = int(res.total.value) / 100.0

        return {
            "success": True,
            "price": price,
            "error_message": False,
            "warning_message": False,
        }

    def clickship_send_shipping(self, pickings) -> list:
        contact = self.clickship_contact
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        res = []
        for picking in pickings:
            booking = sr.book_shipment(picking, contact)
            res.append(booking)
            picking.clickship_tracking_url = booking["tracking_url"]
        return res

    def clickship_get_tracking_link(self, picking) -> str:
        return picking.clickship_tracking_url

    def clickship_cancel_shipment(self, picking) -> None:
        return

    def _clickship_get_default_custom_package_code(self) -> str:
        return ""

    def clickship_get_payment_methods(self) -> str:
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        payment_methods = sr._get_payment_methods()
        return payment_methods[0]
