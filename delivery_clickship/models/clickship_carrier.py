import base64
import logging
from typing import Any

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.stock.models.stock_picking import Picking

from .clickship_request import ClickshipProvider
from .schema import RateResponse

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
    clickship_payment_methods = fields.One2many(
        "clickship.payment_method",
        "delivery_carrier_id",
    )
    clickship_payment_method = fields.Many2one(
        "clickship.payment_method", domain="[('delivery_carrier_id', '=', id)]"
    )

    def clickship_rate_shipment(
        self, order: Picking | SaleOrder
    ) -> dict[str, bool | float]:
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        contact = self.clickship_contact
        res = sr.get_rate(order, contact)
        price = int(res.total.value) / 100.0

        return {
            "success": True,
            "price": price,
            "error_message": False,
            "warning_message": False,
        }

    def clickship_get_raw_rates(self, order: Picking | SaleOrder) -> RateResponse:
        contact = self.clickship_contact
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)

        res = sr.get_raw_rates(order, contact)
        return res

    def clickship_send_shipping(self, pickings: Picking) -> list[dict[str, Any]]:
        contact = self.clickship_contact
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        res: list[dict[str, Any]] = []
        for picking in pickings:
            booking = sr.book_shipment(picking, contact)
            res.append(booking)
            picking.clickship_tracking_url = booking["tracking_url"]
            picking.clickship_shipment_id = booking["shipment_id"]
            att_id = self.env["ir.attachment"].create(  # noqa
                {
                    "name": f"{picking.name} Shipping Label",
                    "type": "binary",
                    "datas": base64.b64encode(booking["label_data"].encode()),
                    "store_fname": f"{picking.name}-ShippingLabel.txt",
                    "res_model": "stock.picking",
                    "res_id": picking.id,
                    "mimetype": "text/plain",
                }
            )
            picking.shipping_label_attachment_id = att_id.id
        return res

    def clickship_get_tracking_link(self, picking: Picking) -> str:
        return picking.clickship_tracking_url

    def clickship_cancel_shipment(self, picking: Picking) -> None:
        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        res = sr.cancel_shipment(picking.clickship_shipment_id)

        if res:
            picking.clickship_shipment_id = None
            picking.clickship_tracking_url = None
            picking.shipping_label_attachment_id.unlink()
        else:
            raise ValidationError(_("Failed to cancel shipment!"))

    def _clickship_get_default_custom_package_code(self) -> str:
        return ""

    def button_get_payment_methods(self) -> None:
        """Fetch payment methods from Clickship and update the model."""
        if not self.clickship_api_key:
            raise ValidationError(_("Clickship API key is not set."))

        self.env["clickship.payment_method"].search(
            [("delivery_carrier_id", "=", self.id)]
        ).unlink()

        sr = ClickshipProvider(self.log_xml, token=self.clickship_api_key)
        payment_methods = sr._get_payment_methods()

        if isinstance(payment_methods, dict):
            return

        method_vals = [
            {
                "name": method["label"],
                "code": method["id"],
                "delivery_carrier_id": self.id,
            }
            for method in payment_methods
        ]
        self.env["clickship.payment_method"].create(method_vals)
