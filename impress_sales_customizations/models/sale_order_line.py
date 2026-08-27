from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    delivered_gross_weight = fields.Float(compute="_compute_delivered_gross_weight")
    ordered_gross_weight = fields.Float(compute="_compute_ordered_gross_weight")

    delivered_net_weight = fields.Float(compute="_compute_delivered_net_weight")
    ordered_net_weight = fields.Float(compute="_compute_ordered_net_weight")

    @api.depends("product_id", "product_uom_qty")
    def _compute_ordered_gross_weight(self):
        for rec in self:
            rec.ordered_gross_weight = rec.product_id.weight * rec.product_uom_qty

    @api.depends("product_id", "qty_delivered")
    def _compute_delivered_gross_weight(self):
        for rec in self:
            rec.delivered_gross_weight = rec.product_id.weight * rec.qty_delivered

    @api.depends("product_id", "product_uom_qty")
    def _compute_ordered_net_weight(self):
        for rec in self:
            rec.ordered_net_weight = rec.product_id.net_weight * rec.product_uom_qty

    @api.depends("product_id", "qty_delivered")
    def _compute_delivered_net_weight(self):
        for rec in self:
            rec.delivered_net_weight = rec.product_id.net_weight * rec.qty_delivered
