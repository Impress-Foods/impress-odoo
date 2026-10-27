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

            picking.delete_labels()

            zpl_data, _ = self.env["ir.actions.report"]._render(
                "delivery_pickup.pickup_delivery_label", [picking.id]
            )
            zpl_attachment = self._pickup_create_label_attachment(
                picking,
                zpl_data,
                label="ZPL",
                extension=".zpl",
                mimetype="text/plain",
            )
            picking.shipping_label_zpl_id = zpl_attachment
            picking.shipping_label_attachment_id = zpl_attachment

            try:
                pdf_data, _ = self.env["ir.actions.report"]._render(
                    "delivery_pickup.pickup_delivery_label_pdf", [picking.id]
                )
            except Exception:
                _logger.exception(
                    "Could not render the PDF pickup label for %s", picking.name
                )
                picking.message_post(
                    body=self.env._("Could not generate the PDF pickup label.")
                )
            else:
                picking.shipping_label_pdf_id = self._pickup_create_label_attachment(
                    picking,
                    pdf_data,
                    label="PDF",
                    extension=".pdf",
                    mimetype="application/pdf",
                )

            res.append(data)
        return res

    def _pickup_create_label_attachment(
        self, picking, data, *, label, extension, mimetype
    ):
        return self.env["ir.attachment"].create(
            {
                "name": f"{picking.name} {label} Shipping Labels{extension}",
                "type": "binary",
                "datas": base64.b64encode(data).decode("utf-8"),
                "res_model": "stock.picking",
                "res_id": picking.id,
                "mimetype": mimetype,
            }
        )

    def pickup_get_tracking_link(self, picking):
        return ""

    def pickup_cancel_shipment(self, picking):
        picking.delete_labels()

    def _pickup_get_default_custom_package_code(self):
        return ""
