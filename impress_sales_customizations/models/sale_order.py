from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_zip = fields.Char(related="partner_shipping_id.zip", store=True)

    port_of_entry = fields.Char()

    delivered_gross_weight = fields.Float(compute="_compute_delivered_gross_weight")
    ordered_gross_weight = fields.Float(compute="_compute_ordered_gross_weight")

    delivered_net_weight = fields.Float(compute="_compute_delivered_net_weight")
    ordered_net_weight = fields.Float(compute="_compute_ordered_net_weight")

    @api.depends("order_line", "order_line.ordered_gross_weight")
    def _compute_ordered_gross_weight(self):
        for rec in self:
            rec.ordered_gross_weight = sum(
                rec.mapped("order_line.ordered_gross_weight")
            )

    @api.depends("order_line", "order_line.delivered_gross_weight")
    def _compute_delivered_gross_weight(self):
        for rec in self:
            rec.delivered_gross_weight = sum(
                rec.mapped("order_line.delivered_gross_weight")
            )

    @api.depends("order_line", "order_line.ordered_net_weight")
    def _compute_ordered_net_weight(self):
        for rec in self:
            rec.ordered_net_weight = sum(rec.mapped("order_line.ordered_net_weight"))

    @api.depends("order_line", "order_line.delivered_net_weight")
    def _compute_delivered_net_weight(self):
        for rec in self:
            rec.delivered_net_weight = sum(
                rec.mapped("order_line.delivered_net_weight")
            )
