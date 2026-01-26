from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    is_residue_order = fields.Boolean(
        compute="_compute_is_residue_order",
        store=True,
    )

    @api.depends("order_line.product_id.is_residue")
    def _compute_is_residue_order(self):
        for order in self:
            order.is_residue_order = any(
                line.product_id.is_residue for line in order.order_line
            )

    def _prepare_picking(self):
        res = super()._prepare_picking()
        if self.is_residue_order:
            residue_picking_type = self.env.ref(
                "impress_residue.picking_type_residue_pickup"
            )
            res["picking_type_id"] = residue_picking_type.id
            res["location_id"] = residue_picking_type.default_location_src_id.id
            res["location_dest_id"] = residue_picking_type.default_location_dest_id.id
        return res


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.depends(
        "move_ids.state",
        "move_ids.scrapped",
        "move_ids.quantity",
        "product_id.is_residue",
    )
    def _compute_qty_received(self):
        # Call super to get the default calculation for non-residue lines
        res = super()._compute_qty_received()

        for line in self:
            if line.product_id.is_residue:
                # Calculate the 'delivered' quantity for residue products
                # This means summing quantities of related stock moves that are
                # 'done' and are part of an 'outgoing' picking type.
                outgoing_moves = line.move_ids.filtered(
                    lambda m: m.state == "done"
                    and m.picking_id
                    and m.picking_id.picking_type_id.code == "outgoing"
                )
                line.qty_received = sum(outgoing_moves.mapped("quantity"))
        return res

    def _prepare_stock_move_vals(
        self, picking, price_unit, product_uom_qty, product_uom
    ):
        res = super()._prepare_stock_move_vals(
            picking, price_unit, product_uom_qty, product_uom
        )
        if self.order_id.is_residue_order:
            residue_picking_type = self.env.ref(
                "impress_residue.picking_type_residue_pickup"
            )
            res["location_id"] = residue_picking_type.default_location_src_id.id
            res["location_dest_id"] = residue_picking_type.default_location_dest_id.id
        return res
