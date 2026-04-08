from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    invoiced_uom_qty = fields.Float(compute="_compute_invoiced_uom_qty")
    received_uom_qty = fields.Float(compute="_compute_received_uom_qty")

    def _compute_invoiced_uom_qty(self):
        for rec in self:
            rec.invoiced_uom_qty = rec.product_uom_id._compute_quantity(
                rec.qty_invoiced, rec.product_id.uom_id
            )

    def _compute_received_uom_qty(self):
        for rec in self:
            rec.received_uom_qty = rec.product_uom_id._compute_quantity(
                rec.qty_received, rec.product_id.uom_id
            )
