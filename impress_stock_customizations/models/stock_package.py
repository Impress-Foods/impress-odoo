from odoo import api, fields, models


class StockPackage(models.Model):
    _inherit = "stock.package"

    net_weight = fields.Float(compute="_compute_net_weight")
    total_count = fields.Float(compute="_compute_total_count")

    @api.depends("contained_quant_ids", "contained_quant_ids.quantity")
    def _compute_total_count(self):
        for rec in self:
            rec.total_count = sum(rec.contained_quant_ids.mapped("quantity"))

    @api.depends("contained_quant_ids", "contained_quant_ids.quantity")
    def _compute_net_weight(self):
        for rec in self:
            rec.net_weight = sum(
                [
                    quant.product_id.net_weight * quant.quantity
                    for quant in rec.contained_quant_ids
                ]
            )
