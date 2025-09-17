import base64
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PickupCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("pickup", "Pick Up")],
        ondelete={
            "pickup": lambda recs: recs.write(
                {"delivery_type": "fixed", "fixed_price": 0}
            )
        },
    )

    def pickup_rate_shipment(self, order):
        return {
            "success": True,
            "price": 0.0,
            "error_message": False,
            "warning_message": False,
        }

    def pickup_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            data = {
                "exact_price": 0,
                "tracking_number": "Pickup",
            }

            report_data, data_format = self.env["ir.actions.report"]._render(
                "delivery_pickup.pickup_delivery_label", [picking.id]
            )
            _logger.warning(report_data)
            att_id = self.env["ir.attachment"].create(
                {
                    "name": f"{picking.name} Shipping Label",
                    "type": "binary",
                    "datas": base64.b64encode(report_data),
                    "store_fname": f"{picking.name}-ShippingLabel.txt",
                    "res_model": "stock.picking",
                    "res_id": picking.id,
                    "mimetype": "text/plain",
                }
            )
            picking.shipping_label_attachment_id = att_id.id
            res.append(data)
        return res

    def pickup_get_tracking_link(self, picking):
        return ""

    def pickup_cancel_shipment(self, picking):
        picking.shipping_label_attachment_id.unlink()

    def _pickup_get_default_custom_package_code(self):
        return ""
