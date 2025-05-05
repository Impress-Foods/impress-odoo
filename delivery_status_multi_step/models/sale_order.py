import logging

from odoo import api, fields, models

from odoo.addons.stock.models.stock_picking import Picking

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_status = fields.Selection(
        selection_add=[
            ("prep_ready", "Ready to Prepare"),
            ("in_prep", "In Preparation"),
            ("ready", "Ready to ship"),
        ]
    )

    @api.depends(
        "picking_ids",
        "picking_ids.state",
        "picking_ids.products_availability_state",
    )
    def _compute_delivery_status(self):
        res = super()._compute_delivery_status()
        for order in self:
            if order.delivery_status not in [False, "full"]:
                prep_pickings: Picking = order.picking_ids.filtered_domain(
                    [("picking_type_id.code", "=", "internal")]
                )
                deliveries: Picking = order.picking_ids - prep_pickings

                deliveries_availability = deliveries.mapped(
                    "products_availability_state"
                )
                prep_pickings_status = prep_pickings.mapped("state")

                # Compute some conditions to increase readability in match statement
                prep_started = any(
                    [status in ["done"] for status in prep_pickings_status]
                )

                all_prep_done = all(
                    [status in ["done"] for status in prep_pickings_status]
                )

                all_prep_done_or_cancelled = all(
                    [status in ["done", "cancel"] for status in prep_pickings_status]
                )

                all_prep_assigned_or_cancelled = all(
                    [
                        status in ["assigned", "cancelled"]
                        for status in prep_pickings_status
                    ]
                )

                all_deliveries_available = all(
                    [
                        availability == "available"
                        for availability in deliveries_availability
                    ]
                )

                if all_deliveries_available and all_prep_done_or_cancelled:
                    order.delivery_status = "ready"

                elif prep_started and not all_prep_done:
                    order.delivery_status = "in_prep"

                elif all_prep_assigned_or_cancelled:
                    order.delivery_status = "prep_ready"

                else:
                    pass

        return res
