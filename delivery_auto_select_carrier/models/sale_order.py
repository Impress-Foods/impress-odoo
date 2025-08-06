import logging
from ast import literal_eval

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    auto_selected_carrier_id = fields.Many2one(
        "delivery.carrier", compute="_compute_auto_selected_carrier_id", store=True
    )

    @api.depends("partner_id")
    def _compute_auto_selected_carrier_id(self):
        for rec in self:
            if not rec._compute_propagate_auto_carrier_id():
                rec.auto_selected_carrier_id = False
                continue

            # get available carriers
            carrier_id = self.env["delivery.carrier"].search([])
            # Arbitrary default carrier required by the wizard
            if carrier_id:
                carrier_id = carrier_id[0]

            else:
                rec.auto_selected_carrier_id = False
                continue

            wizard = self.env["choose.delivery.carrier"].create(
                {
                    "partner_id": rec.partner_shipping_id.id,
                    "order_id": rec.id,
                    "carrier_id": carrier_id.id,
                }
            )
            available_carriers = self._get_auto_select_carriers(wizard)

            wizard.unlink()  # delete the wizard as soon as possible

            if available_carriers:
                rec.auto_selected_carrier_id = available_carriers[0]
            else:
                rec.auto_selected_carrier_id = False

    @api.model
    def _get_auto_select_carriers(self, wizard):
        # We get the highest priority carrier. Arbitrary selection
        # when multiple carriers with the same priority are available
        return wizard.available_carrier_ids.filtered("can_be_auto_selected").sorted(
            key="priority", reverse=True
        )

    def _compute_propagate_auto_carrier_id(self):
        # Computes if we should auto select a carrier for the
        # Sale Order based on the domain in the settings

        domain = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("delivery_auto_select_carrier.domain")
        )

        if not domain:
            return False

        if isinstance(domain, str):
            domain = literal_eval(domain)

        res = self.id in self.env["sale.order"].search(domain).mapped("id")
        return res

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            if order._compute_propagate_auto_carrier_id():
                picking = self.picking_ids.filtered_domain(
                    [("picking_type_code", "=", "outgoing")]
                )
                picking.carrier_id = self.auto_selected_carrier_id
        return res
