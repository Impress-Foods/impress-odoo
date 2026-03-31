from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    sale_customer_ref = fields.Char(
        string="Customer Reference", related="sale_line_id.order_id.client_order_ref"
    )

    @api.model
    def _get_qty_to_fulfill_by_moves(self, moves) -> dict[int, float]:
        """Batch compute qty_to_fulfill for a recordset of moves.

        Returns a dict mapping move_id -> qty_to_fulfill (product_uom_qty - promised).
        Uses a single read_group instead of one search per move.
        """
        result = {m.id: m.product_uom_qty for m in moves}
        if not moves:
            return result

        groups = self.env["mrp.campaign.demand.target"].read_group(
            [("target_model", "=", "stock.move"), ("target_id", "in", moves.ids)],
            ["target_id", "promised_qty:sum"],
            ["target_id"],
        )
        for group in groups:
            target_id = group["target_id"]
            if isinstance(target_id, list | tuple):
                target_id = target_id[0]
            if target_id in result:
                result[target_id] -= group["promised_qty"]
        return result

    def _get_qty_to_fulfill(self) -> float:
        self.ensure_one()
        return self._get_qty_to_fulfill_by_moves(self)[self.id]
