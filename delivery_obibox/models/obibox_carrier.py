import base64
import logging
from typing import Any

from odoo import fields, models

from odoo.addons.base.models.res_partner import Partner
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.stock.models.stock_picking import Picking

from .obibox_request import ObiboxProvider

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
    obibox_username = fields.Char()
    obibox_label_format = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("zpl", "ZPL"),
        ],
        string="Label Format",
        default="zpl",
        help="Format of the label to be printed.",
    )

    obibox_delivery_day = fields.Selection(
        selection=[
            ("mon", "Monday"),
            ("tue", "Tuesday"),
            ("wed", "Wednesday"),
            ("thu", "Thursday"),
            ("fri", "Friday"),
        ],
        default="mon",
    )

    def obibox_rate_shipment(self, order: Picking | SaleOrder) -> dict:
        sr = ObiboxProvider(
            self.log_xml, username=self.obibox_username, token=self.obibox_api_key
        )
        res = sr.get_rate(order)
        return res

    def obibox_send_shipping(self, pickings: Picking) -> list:
        sr = ObiboxProvider(
            self.log_xml, username=self.obibox_username, token=self.obibox_api_key
        )
        res: list[dict[str, Any]] = []

        for picking in pickings:
            booking = sr.book_shipment(picking)

            res.append(booking)
            tracking_numbers = ",".join(
                [x.tracking_number for x in booking["trackings"]]
            )
            picking.obibox_tracking_numbers = tracking_numbers  # type: ignore
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
            picking.shipping_label_attachment_id = att_id.id  # type: ignore
        return res

    def obibox_get_tracking_link(self, picking: Picking) -> str:
        self.ensure_one()
        return f"https://tracking.obibox.io/{picking.carrier_tracking_ref}"

    def obibox_cancel_shipment(self, pickings: Picking) -> None:
        sr = ObiboxProvider(
            self.log_xml, username=self.obibox_username, token=self.obibox_api_key
        )
        for picking in pickings:
            sr.cancel_shipment(picking)
            picking.shipping_label_attachment_id.unlink()  # type: ignore

    def _obibox_get_default_custom_package_code(self) -> str:
        return ""

    def _match_address(self, partner: Partner):
        res = super()._match_address(partner)

        if self.delivery_type == "obibox":
            sr = ObiboxProvider(
                self.log_xml, username=self.obibox_username, token=self.obibox_api_key
            )
            res = sr.check_coverage(partner)
        return res
