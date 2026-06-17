from ast import literal_eval

from odoo import api, fields, models
from odoo.fields import Domain


class SaleOrder(models.Model):
    _inherit = "sale.order"

    auto_selected_carrier_id = fields.Many2one(
        "delivery.carrier", compute="_compute_auto_selected_carrier_id", store=True
    )

    @api.depends("partner_shipping_id")
    def _compute_auto_selected_carrier_id(self) -> None:
        domain = Domain("can_be_auto_selected", "=", True)

        for rec in self:
            if not rec.partner_id.zip:
                rec.auto_selected_carrier_id = False
                continue
            if (
                not rec._compute_propagate_auto_carrier_id()
                and not self.env.context.get("auto_select_carrier_manual")
            ):
                rec.auto_selected_carrier_id = False
                continue
            auto_selectable_carriers = self.env["delivery.carrier"].search(
                domain
                + self.env["delivery.carrier"]._check_company_domain(rec.company_id)
            )

            available = auto_selectable_carriers.available_carriers(
                rec.partner_shipping_id, rec
            )

            rec.auto_selected_carrier_id = available.sorted(
                key="priority", reverse=True
            )[:1]

    def _compute_propagate_auto_carrier_id(self) -> bool:
        # Computes if we should auto select a carrier for the
        # Sale Order based on the domain in the settings

        # Short circuit if the partner is public user
        # Happens when user is in eCommerce checkout and
        # not logged in
        if self.partner_id.id == self.env.ref("base.public_partner").id:
            return False

        domain = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("delivery_auto_select_carrier.domain")
        )

        if isinstance(domain, str):
            domain = Domain(literal_eval(domain) if domain else [])
        else:
            domain = Domain.TRUE

        domain &= Domain("id", "=", self.id)
        res = self.env["sale.order"].search_count(domain)
        return res

    def _action_confirm(self) -> None:
        res = super()._action_confirm()
        for order in self:
            if order._compute_propagate_auto_carrier_id():
                order._compute_auto_selected_carrier_id()
                picking = order.picking_ids.filtered_domain(
                    [("picking_type_code", "=", "outgoing")]
                )
                picking.carrier_id = order.auto_selected_carrier_id
        return res

    def action_auto_select_carrier(self) -> None:
        self.with_context(
            auto_select_carrier_manual=True
        )._compute_auto_selected_carrier_id()
        for rec in self:
            if (
                rec._compute_propagate_auto_carrier_id()
                and rec.auto_selected_carrier_id
            ):
                domain = Domain("picking_type_code", "=", "outgoing") & Domain(
                    "state", "in", ["draft", "waiting", "confirmed", "assigned"]
                )
                pickings = rec.picking_ids.filtered_domain(domain)
                pickings.carrier_id = rec.auto_selected_carrier_id
