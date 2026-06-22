import base64
import logging
from typing import Any

from odoo import fields, models

from odoo.addons.base.models.res_partner import ResPartner
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.stock.models.stock_picking import StockPicking

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

    obibox_api_key = fields.Char(string="Obibox Key")
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
        help="Select the day when the package will be picked up.",
    )

    def obibox_rate_shipment(self, order: StockPicking | SaleOrder) -> dict:
        sr = self._get_provider()
        res = sr.get_rate(order)
        return res

    def obibox_send_shipping(self, pickings: StockPicking) -> list:
        sr = self._get_provider()
        res: list[dict[str, Any]] = []

        for picking in pickings:
            booking = sr.book_shipment(picking)

            res.append(booking)
            tracking_numbers = ",".join(
                [x.tracking_number for x in booking["trackings"]]
            )
            picking.obibox_tracking_numbers = tracking_numbers
            att_id = self.env["ir.attachment"].create(
                {
                    "name": f"{picking.name} Shipping Label",
                    "type": "binary",
                    "datas": base64.b64encode(booking["label_data"].encode()).decode(
                        "utf-8"
                    ),
                    "store_fname": f"{picking.name}-ShippingLabel.txt",
                    "res_model": "stock.picking",
                    "res_id": picking.id,
                    "mimetype": "text/plain",
                }
            )
            picking.shipping_label_attachment_id = att_id.id
        return res

    def obibox_get_tracking_link(self, picking: StockPicking) -> str:
        self.ensure_one()
        return f"https://tracking.obibox.io/{picking.carrier_tracking_ref}"

    def obibox_cancel_shipment(self, pickings: StockPicking) -> None:
        sr = self._get_provider()
        for picking in pickings:
            sr.cancel_shipment(picking)
            picking.shipping_label_attachment_id.unlink()
            picking.obibox_tracking_numbers = ""

    def _obibox_get_default_custom_package_code(self) -> str:
        return ""

    def _match_address(self, partner: ResPartner) -> bool:
        if self.delivery_type == "obibox":
            res: bool = self._check_coverage(partner)
        else:
            res: bool = super()._match_address(partner)
        return res

    def _check_coverage(self, partner: ResPartner) -> bool:
        res: bool = False
        if partner.zip:
            if partner.obibox_coverage_checked:
                res = partner.obibox_coverage
            else:
                sr = self._get_provider()
                res = sr.check_coverage(partner)
                partner.obibox_coverage = res
        partner.obibox_coverage_checked = True
        return res

    def _get_provider(self) -> bool:
        self.ensure_one()
        if self.delivery_type == "obibox":
            return ObiboxProvider(
                self.log_xml,
                self.env,
                prod_environment=self.prod_environment,
                username=self.obibox_username,
                token=self.obibox_api_key,
            )
        return super()._get_provider()
